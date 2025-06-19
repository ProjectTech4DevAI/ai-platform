import inspect
import logging
import time
import warnings
from uuid import UUID, uuid4
from typing import Any, List, Optional
from dataclasses import dataclass, field, fields, asdict, replace

from openai import OpenAI, OpenAIError
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi import Path as FastPath
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.exc import NoResultFound, MultipleResultsFound, SQLAlchemyError

from app.api.deps import CurrentUser, SessionDep, CurrentUserOrgproject
from app.core.cloud import AmazonCloudStorage
from app.core.config import settings
from app.core.util import now, raise_from_unknown, post_callback
from app.crud import DocumentCrud, CollectionCrud, DocumentCollectionCrud
from app.crud.rag import OpenAIVectorStoreCrud, OpenAIAssistantCrud
from app.models import Collection, Document
from app.utils import APIResponse, load_description

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
    documents: List[UUID] = Field(
        description="List of document IDs",
    )
    batch_size: int = Field(
        default=1,
        description=(
            "Number of documents to send to OpenAI in a single "
            "transaction. See the `file_ids` parameter in the "
            "vector store [create batch](https://platform.openai.com/docs/api-reference/vector-stores-file-batches/createBatch)."
        ),
    )

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
    model: str = Field(
        description=(
            "OpenAI model to attach to this assistant. The model "
            "must compatable with the assistants API; see the "
            "OpenAI [model documentation](https://platform.openai.com/docs/models/compare) for more."
        ),
    )
    instructions: str = Field(
        description=(
            "Assistant instruction. Sometimes referred to as the " '"system" prompt.'
        ),
    )
    temperature: float = Field(
        default=1e-6,
        description=(
            "Model temperature. The default is slightly "
            "greater-than zero because it is [unknown how OpenAI "
            "handles zero](https://community.openai.com/t/clarifications-on-setting-temperature-0/886447/5)."
        ),
    )


class CallbackRequest(BaseModel):
    callback_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL to call to report endpoint status",
    )


class CreationRequest(
    DocumentOptions,
    AssistantOptions,
    CallbackRequest,
):
    def extract_super_type(self, cls: "CreationRequest"):
        for field_name in cls.__fields__.keys():
            field_value = getattr(self, field_name)
            yield (field_name, field_value)


class DeletionRequest(CallbackRequest):
    collection_id: UUID = Field("Collection to delete")


class CallbackHandler:
    def __init__(self, payload: ResponsePayload):
        self.payload = payload

    def fail(self, body):
        raise NotImplementedError()

    def success(self, body):
        raise NotImplementedError()


class SilentCallback(CallbackHandler):
    def fail(self, body):
        return

    def success(self, body):
        return


class WebHookCallback(CallbackHandler):
    def __init__(self, url: HttpUrl, payload: ResponsePayload):
        super().__init__(payload)
        self.url = url

    def __call__(self, response: APIResponse, status: str):
        time = ResponsePayload.now()
        payload = replace(self.payload, status=status, time=time)
        response.metadata = asdict(payload)

        post_callback(self.url, response)

    def fail(self, body):
        self(APIResponse.failure_response(body), "incomplete")

    def success(self, body):
        self(APIResponse.success_response(body), "complete")


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
    start_time = time.time()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    if request.callback_url is None:
        callback = SilentCallback(payload)
    else:
        callback = WebHookCallback(request.callback_url, payload)

    #
    # Create the assistant and vector store
    #

    vector_store_crud = OpenAIVectorStoreCrud(client)
    try:
        vector_store = vector_store_crud.create()
    except OpenAIError as err:
        callback.fail(str(err))
        return

    storage = AmazonCloudStorage(current_user)
    document_crud = DocumentCrud(session, current_user.id)
    assistant_crud = OpenAIAssistantCrud(client)

    docs = request(document_crud)
    log_doc = list(docs)
    doc_count = len(log_doc)
    flat_docs = [doc for sublist in log_doc for doc in sublist]
    file_exts = list(
        {doc.fname.split(".")[-1] for doc in flat_docs if "." in doc.fname}
    )

    file_sizes_kb = []
    for doc in flat_docs:
        size_kb = storage.get_file_size_kb(doc.object_store_url)
        file_sizes_kb.append(size_kb)

    kwargs = dict(request.extract_super_type(AssistantOptions))
    try:
        updates = vector_store_crud.update(vector_store.id, storage, docs)
        documents = list(updates)
        assistant = assistant_crud.create(vector_store.id, **kwargs)
    except Exception as err:  # blanket to handle SQL and OpenAI errors
        logging.error(f"File Search setup error: {err} ({type(err).__name__})")
        vector_store_crud.delete(vector_store.id)
        callback.fail(str(err))
        return

    #
    # Store the results
    #

    collection_crud = CollectionCrud(session, current_user.id)
    try:
        collection_crud = CollectionCrud(session, current_user.id)
        collection = collection_crud.read_one(UUID(payload.key))
        collection.llm_service_id = assistant.id
        collection.llm_service_name = request.model
        collection.status = "Successful"
        collection.updated_at = now()

        dc_crud = DocumentCollectionCrud(session)
        dc_crud.create(collection, documents)

        collection_crud._update(collection)
    except SQLAlchemyError as err:
        _backout(assistant_crud, assistant.id)
        logging.error(f"[Error during creating colletion - {err}")
        callback.fail(str(err))
        return

    elapsed = time.time() - start_time
    logging.info(
        f"Collection created: {collection.id} | "
        f"Time: {elapsed}s | Files: {doc_count} |Sizes:{file_sizes_kb} KB |Types: {file_exts}"
    )

    #
    # Send back successful response
    #

    callback.success(collection.model_dump(mode="json"))


@router.post(
    "/create",
    description=load_description("collections/create.md"),
)
def create_collection(
    session: SessionDep,
    current_user: CurrentUserOrgproject,
    request: CreationRequest,
    background_tasks: BackgroundTasks,
):
    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload("processing", route)

    # 1. Create initial collection record
    collection = Collection(
        id=UUID(payload.key),
        owner_id=current_user.id,
        organization_id=current_user.organization_id,
        project_id=current_user.project_id,
        status="processing",
    )

    collection_crud = CollectionCrud(session, current_user.id)
    collection_crud.create(collection, documents=[])

    # 2. Launch background task
    background_tasks.add_task(
        do_create_collection,
        session,
        current_user,
        request,
        payload,
    )

    return APIResponse.success_response(data=None, metadata=asdict(payload))


def do_delete_collection(
    session: SessionDep,
    current_user: CurrentUser,
    request: DeletionRequest,
    payload: ResponsePayload,
):
    if request.callback_url is None:
        callback = SilentCallback(payload)
    else:
        callback = WebHookCallback(request.callback_url, payload)

    collection_crud = CollectionCrud(session, current_user.id)
    try:
        collection = collection_crud.read_one(request.collection_id)
        assistant = OpenAIAssistantCrud()
        data = collection_crud.delete(collection, assistant)
        callback.success(data.model_dump(mode="json"))
    except (ValueError, PermissionError, SQLAlchemyError) as err:
        callback.fail(str(err))
    except Exception as err:
        warnings.warn(
            'Unexpected exception "{}": {}'.format(type(err).__name__, err),
        )
        callback.fail(str(err))


@router.post(
    "/delete",
    description=load_description("collections/delete.md"),
)
def delete_collection(
    session: SessionDep,
    current_user: CurrentUser,
    request: DeletionRequest,
    background_tasks: BackgroundTasks,
):
    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload("processing", route)

    background_tasks.add_task(
        do_delete_collection,
        session,
        current_user,
        request,
        payload,
    )

    return APIResponse.success_response(data=None, metadata=asdict(payload))


@router.post(
    "/info/{collection_id}",
    description=load_description("collections/info.md"),
    response_model=APIResponse[Collection],
)
def collection_info(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID = FastPath(description="Collection to retrieve"),
):
    collection_crud = CollectionCrud(session, current_user.id)
    data = collection_crud.read_one(collection_id)
    return APIResponse.success_response(data)


@router.post(
    "/list",
    description=load_description("collections/list.md"),
    response_model=APIResponse[List[Collection]],
)
def list_collections(
    session: SessionDep,
    current_user: CurrentUser,
):
    collection_crud = CollectionCrud(session, current_user.id)
    data = collection_crud.read_all()
    return APIResponse.success_response(data)


@router.post(
    "/docs/{collection_id}",
    description=load_description("collections/docs.md"),
    response_model=APIResponse[List[Document]],
)
def collection_documents(
    session: SessionDep,
    current_user: CurrentUser,
    collection_id: UUID = FastPath(description="Collection to retrieve"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    collection_crud = CollectionCrud(session, current_user.id)
    document_collection_crud = DocumentCollectionCrud(session)
    collection = collection_crud.read_one(collection_id)
    data = document_collection_crud.read(collection, skip, limit)
    return APIResponse.success_response(data)
