import sys
import inspect
import warnings
from uuid import UUID, uuid4
from typing import Any, Callable, List
from dataclasses import dataclass, field, fields, asdict, replace

from openai import OpenAI, OpenAIError
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.util import now, raise_from_unknown
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

    def __call__(self, crud: DocumentCrud):
        (start, stop) = (0, self.batch_size)
        while True:
            view = self.documents[start:stop]
            if not view:
                break
            yield crud.read_each(view)
            start = stop
            stop += self.batch_size


# Fields to be passed along to OpenAI. They must be a subset of
# parameters accepted by the OpenAI.clien.beta.assistants.create API.
class AssistantOptions(BaseModel):
    model: str
    instructions: str
    temperature: float = 1e-6


class CreationRequest(DocumentOptions, AssistantOptions):
    pass


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

    #
    # Create the assistant and vector store
    #

    v_crud = OpenAIVectorStoreCrud(client)
    try:
        vector_store = v_crud.create()
    except OpenAIError as err:
        raise HTTPException(status_code=507, detail=str(err))

    d_crud = DocumentCrud(session, current_user.id)
    a_crud = OpenAIAssistantCrud(client)
    kwargs = {x: getattr(request, x) for x in bm_fields(AssistantOptions)}
    try:
        documents = list(v_crud.update(vector_store.id, request(d_crud)))
        assistant = a_crud.create(v_crud.read(vector_store.id), **kwargs)
    except (InterruptedError, OpenAIError, CloudStorageError) as err:
        raise HTTPException(status_code=507, detail=str(err))
    except SQLAlchemyError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)
    finally:
        if any(sys.exc_info()):  # this works because every except raises
            v_crud.delete(vector_store.id)

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
        raise HTTPException(status_code=400, detail=str(err))

    #
    # Send back successful response
    #

    payload = replace(
        payload,
        status="complete",
        time=ResponsePayload.now(),
        body=collection.model_dump(),
    )

    return payloaded_response(payload)


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


@router.post("/delete/{collection_id}", response_model=APIResponse[Collection])
def delete_collection(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID,
):
    c_crud = CollectionCrud(session)
    collection = c_crud.delete(collection_id)

    a_crud = OpenAIAssistantCrud()
    a_crud.delete(collection.llm_service_id)

    return APIResponse.success_response(collection)
