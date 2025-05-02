import inspect
import logging
import warnings
from uuid import UUID, uuid4
from typing import Any, List
from dataclasses import dataclass, field, fields, asdict, replace

from openai import OpenAI, OpenAIError
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy.exc import NoResultFound, MultipleResultsFound, SQLAlchemyError

from app.api.deps import CurrentUser, SessionDep
from app.core.cloud import AmazonCloudStorage
from app.core.config import settings
from app.core.util import now, raise_from_unknown, post_callback
from app.crud import DocumentCrud, CollectionCrud, DocumentCollectionCrud
from app.crud.rag import OpenAIVectorStoreCrud, OpenAIAssistantCrud
from app.models import Collection, Document
from app.utils import APIResponse

router = APIRouter(prefix="/collections", tags=["collections"])


@dataclass
class ResponsePayload:
    status: str
    route: str
    key: str = field(default_factory=lambda: str(uuid4()))
    time: str = field(default_factory=lambda: now().strftime("%c"))

    @classmethod
    def now(cls):
        attr = "time"
        for i in fields(cls):
            if i.name == attr:
                return i.default_factory()

        raise AttributeError(f'Expected attribute "{attr}" does not exist')


class DocumentOptions(BaseModel):
    documents: List[UUID]
    batch_size: int = 1

    def model_post_init(self, __context: Any):
        self.documents = list(set(self.documents))

    def __call__(self, crud: DocumentCrud):
        (start, stop) = (0, self.batch_size)
        while True:
            view = self.documents[start:stop]
            if not view:
                break
            yield crud.read_each(view)
            start = stop
            stop += self.batch_size


class AssistantOptions(BaseModel):
    # Fields to be passed along to OpenAI. They must be a subset of
    # parameters accepted by the OpenAI.clien.beta.assistants.create
    # API.
    model: str
    instructions: str
    temperature: float = 1e-6


class CreationRequest(DocumentOptions, AssistantOptions):
    callback_url: HttpUrl


class CallbackHandler:
    def __init__(self, url: HttpUrl, payload: ResponsePayload):
        self.url = url
        self.payload = payload

    def __call__(self, response: APIResponse, status: str):
        time = ResponsePayload.now()
        payload = replace(self.payload, status=status, time=time)
        response.metadata = asdict(payload)

        post_callback(self.url, response)

    def fail(self, body):
        self(APIResponse.failure_response(body), "incomplete")

    def success(self, body):
        self(APIResponse.success_response(body), "complete")


def bm_fields(cls: BaseModel):
    yield from cls.__fields__.keys()


def _backout(crud: OpenAIAssistantCrud, assistant_id: str):
    try:
        crud.delete(assistant_id)
    except OpenAIError:
        warnings.warn(
            ": ".join(
                [
                    f"Unable to remove assistant {assistant_id}",
                    "platform DB may be out of sync with OpenAI",
                ]
            )
        )


def do_create_collection(
    session: SessionDep,
    current_user: CurrentUser,
    request: CreationRequest,
    payload: ResponsePayload,
):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    callback = CallbackHandler(request.callback_url, payload)

    #
    # Create the assistant and vector store
    #

    v_crud = OpenAIVectorStoreCrud(client)
    try:
        vector_store = v_crud.create()
    except OpenAIError as err:
        callback.fail(str(err))
        return

    storage = AmazonCloudStorage(current_user)
    d_crud = DocumentCrud(session, current_user.id)
    a_crud = OpenAIAssistantCrud(client)

    kwargs = {x: getattr(request, x) for x in bm_fields(AssistantOptions)}
    docs = request(d_crud)
    try:
        documents = list(v_crud.update(vector_store.id, storage, docs))
        assistant = a_crud.create(vector_store.id, **kwargs)
    except Exception as err:  # blanket to handle SQL and OpenAI errors
        logging.error(f"File Search setup error: {err} ({type(err).__name__})")
        v_crud.delete(vector_store.id)
        callback.fail(str(err))
        return

    #
    # Store the results
    #

    c_crud = CollectionCrud(session, current_user.id)
    collection = Collection(
        llm_service_id=assistant.id,
        llm_service_name=request.model,
    )
    try:
        c_crud.create(collection, documents)
    except SQLAlchemyError as err:
        _backout(a_crud, assistant.id)
        callback.fail(str(err))
        return

    #
    # Send back successful response
    #

    callback.success(collection.model_dump(mode="json"))


@router.post("/create")
def create_collection(
    session: SessionDep,
    current_user: CurrentUser,
    request: CreationRequest,
    background_tasks: BackgroundTasks,
):
    if not settings.OPENAI_API_KEY:
        detail = "OpenAI key not specified"
        raise HTTPException(status_code=400, detail=detail)

    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload("processing", route)

    background_tasks.add_task(
        do_create_collection,
        session,
        current_user,
        request,
        payload,
    )

    return APIResponse.success_response(data=None, metadata=asdict(payload))


@router.post("/delete/{collection_id}", response_model=APIResponse[Collection])
def delete_collection(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID,
):
    c_crud = CollectionCrud(session, current_user.id)
    try:
        collection = c_crud.read_one(collection_id)
        data = c_crud.delete(collection, OpenAIAssistantCrud)
    except (ValueError, SQLAlchemyError) as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    return APIResponse.success_response(data)


@router.post("/info/{collection_id}", response_model=APIResponse[Collection])
def collection_info(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID,
):
    c_crud = CollectionCrud(session, current_user.id)
    try:
        data = c_crud.read_one(collection_id)
    except NoResultFound as err:
        raise HTTPException(status_code=404, detail=str(err))
    except MultipleResultsFound as err:
        raise HTTPException(status_code=503, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    return APIResponse.success_response(data)


@router.post("/list", response_model=APIResponse[List[Collection]])
def list_collections(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    c_crud = CollectionCrud(session, current_user.id)
    try:
        data = c_crud.read_many(skip, limit)
    except (ValueError, SQLAlchemyError) as err:
        raise HTTPException(status_code=403, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    return APIResponse.success_response(data)


@router.post(
    "/docs/{collection_id}",
    response_model=APIResponse[List[Document]],
)
def collection_documents(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    c_crud = CollectionCrud(session, current_user.id)
    dc_crud = DocumentCollectionCrud(session)
    try:
        data = dc_crud.read(c_crud.read_one(collection_id), skip, limit)
    except (SQLAlchemyError, ValueError) as err:
        raise HTTPException(status_code=400, detail=str(err))

    return APIResponse.success_response(data)
