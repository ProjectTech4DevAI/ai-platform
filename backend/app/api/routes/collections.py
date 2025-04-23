import sys
import inspect
import logging
import warnings
from uuid import UUID, uuid4
from typing import Any, Callable, List
from dataclasses import dataclass, field, fields, asdict, replace

from openai import OpenAI, OpenAIError
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import CurrentUser, SessionDep
from app.core.cloud import AmazonCloudStorage
from app.core.config import settings
from app.core.util import now, raise_from_unknown, post_callback
from app.crud import DocumentCrud, CollectionCrud
from app.crud.rag import OpenAIVectorStoreCrud, OpenAIAssistantCrud
from app.models import Collection
from app.utils import APIResponse

from app.core.cloud import CloudStorageError

router = APIRouter(prefix="/collections", tags=["collections"])


@dataclass
class ResponsePayload:
    status: str
    route: str
    key: str = field(default_factory=lambda: str(uuid4()))
    time: str = field(default_factory=lambda: now().strftime("%c"))
    body: Any = None

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

    def __call__(self, status: str, body: Any):
        time = ResponsePayload.now()
        payload = replace(self.payload, status=status, time=time, body=body)
        post_callback(self.url, payloaded_response(payload))

    def fail(self, body):
        self("failure", body)

    def success(self, body):
        self("success", body)


def bm_fields(cls: BaseModel):
    yield from cls.__fields__.keys()


def payloaded_response(payload: ResponsePayload):
    return APIResponse.success_response(data=asdict(payload))


def _backout(crud: OpenAIAssistantCrud, assistant_id: str):
    try:
        a_crud.delete(assistant.id)
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

    callback.success(collection.model_dump())


@router.post("/mk")
def make_collection(
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

    return payloaded_response(payload)


@router.post("/rm/{collection_id}", response_model=APIResponse[Collection])
def remove_collection(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID,
):
    c_crud = CollectionCrud(session)
    a_crud = OpenAIAssistantCrud()
    try:
        collection = c_crud.delete(collection_id)
        a_crud.delete(collection.llm_service_id)
    except SQLAlchemyError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return APIResponse.success_response(collection)


@router.post("/stat/{collection_id}", response_model=APIResponse[Collection])
def collection_info(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID,
):
    c_crud = CollectionCrud(session, current_user.id)
    try:
        data = c_crud.read(collection_id)
    except SQLAlchemyError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return APIResponse.success_response(data)


@router.post("/docs/{collection_id}", response_model=APIResponse[Collection])
def collection_documents(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    dc_crud = DocumentCollectionCrud(session, current_user.id)
    try:
        data = dc_crud.read(collection_id)
    except (SQLAlchemyError, ValueError) as err:
        raise HTTPException(status_code=400, detail=str(err))

    return APIResponse.success_response(data)
