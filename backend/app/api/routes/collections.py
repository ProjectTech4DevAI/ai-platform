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

from app.api.deps import CurrentUser, SessionDep, CurrentUserOrgProject
from app.core.cloud import AmazonCloudStorage
from app.core.config import settings
from app.core.util import now, raise_from_unknown, post_callback
from app.crud import DocumentCrud, CollectionCrud, DocumentCollectionCrud
from app.crud.rag import OpenAIVectorStoreCrud, OpenAIAssistantCrud
from app.models import Collection, Document
from app.models.collection import CollectionStatus
from app.utils import APIResponse, load_description

logger = logging.getLogger(__name__)
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
        logger.info(
            f"[DocumentOptions.model_post_init] Deduplicating document IDs | {{'document_count': {len(self.documents)}}}"
        )
        self.documents = list(set(self.documents))

    def __call__(self, crud: DocumentCrud):
        logger.info(
            f"[DocumentOptions.call] Starting batch iteration for documents | {{'batch_size': {self.batch_size}, 'total_documents': {len(self.documents)}}}"
        )
        (start, stop) = (0, self.batch_size)
        while True:
            view = self.documents[start:stop]
            if not view:
                break
            logger.info(
                f"[DocumentOptions.call] Yielding document batch | {{'start': {start}, 'stop': {stop}, 'batch_document_count': {len(view)}}}"
            )
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
        logger.info(
            f"[CreationRequest.extract_super_type] Extracting fields for {cls.__name__} | {{'field_count': {len(cls.__fields__)}}}"
        )
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
        logger.info(
            f"[SilentCallback.fail] Silent callback failure | {{'body': '{body}'}}"
        )
        return

    def success(self, body):
        logger.info(
            f"[SilentCallback.success] Silent callback success | {{'body': '{body}'}}"
        )
        return


class WebHookCallback(CallbackHandler):
    def __init__(self, url: HttpUrl, payload: ResponsePayload):
        super().__init__(payload)
        self.url = url
        logger.info(
            f"[WebHookCallback.init] Initialized webhook callback | {{'url': '{url}', 'payload_key': '{payload.key}'}}"
        )

    def __call__(self, response: APIResponse, status: str):
        time = ResponsePayload.now()
        payload = replace(self.payload, status=status, time=time)
        response.metadata = asdict(payload)
        logger.info(
            f"[WebHookCallback.call] Posting callback | {{'url': '{self.url}', 'status': '{status}', 'payload_key': '{payload.key}'}}"
        )
        post_callback(self.url, response)

    def fail(self, body):
        logger.error(f"[WebHookCallback.fail] Callback failed | {{'body': '{body}'}}")
        self(APIResponse.failure_response(body), "incomplete")

    def success(self, body):
        logger.info(
            f"[WebHookCallback.success] Callback succeeded | {{'body': '{body}'}}"
        )
        self(APIResponse.success_response(body), "complete")


def _backout(crud: OpenAIAssistantCrud, assistant_id: str):
    try:
        logger.info(
            f"[backout] Attempting to delete assistant | {{'assistant_id': '{assistant_id}'}}"
        )
        crud.delete(assistant_id)
    except OpenAIError as err:
        logger.error(
            f"[backout] Failed to delete assistant | {{'assistant_id': '{assistant_id}', 'error': '{str(err)}'}}"
        )
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
    callback = (
        SilentCallback(payload)
        if request.callback_url is None
        else WebHookCallback(request.callback_url, payload)
    )

    storage = AmazonCloudStorage(current_user)
    document_crud = DocumentCrud(session, current_user.id)
    assistant_crud = OpenAIAssistantCrud(client)
    vector_store_crud = OpenAIVectorStoreCrud(client)
    collection_crud = CollectionCrud(session, current_user.id)

    try:
        vector_store = vector_store_crud.create()

        docs = list(request(document_crud))
        flat_docs = [doc for sublist in docs for doc in sublist]

        file_exts = {doc.fname.split(".")[-1] for doc in flat_docs if "." in doc.fname}
        file_sizes_kb = [
            storage.get_file_size_kb(doc.object_store_url) for doc in flat_docs
        ]

        logging.info(
            f"[VectorStore Update] Uploading {len(flat_docs)} documents to vector store {vector_store.id}"
        )
        list(vector_store_crud.update(vector_store.id, storage, docs))
        logging.info(f"[VectorStore Upload] Upload completed")

        assistant_options = dict(request.extract_super_type(AssistantOptions))
        logging.info(
            f"[Assistant Create] Creating assistant with options: {assistant_options}"
        )
        assistant = assistant_crud.create(vector_store.id, **assistant_options)
        logging.info(f"[Assistant Create] Assistant created: {assistant.id}")

        collection = collection_crud.read_one(UUID(payload.key))
        collection.llm_service_id = assistant.id
        collection.llm_service_name = request.model
        collection.status = CollectionStatus.successful
        collection.updated_at = now()

        if flat_docs:
            logging.info(
                f"[DocumentCollection] Linking {len(flat_docs)} documents to collection {collection.id}"
            )
            DocumentCollectionCrud(session).create(collection, flat_docs)

        collection_crud._update(collection)

        elapsed = time.time() - start_time
        logging.info(
            f"Collection created: {collection.id} | Time: {elapsed:.2f}s | "
            f"Files: {len(flat_docs)} | Sizes: {file_sizes_kb} KB | Types: {list(file_exts)}"
        )
        callback.success(collection.model_dump(mode="json"))

    except Exception as err:
        logging.error(f"[Collection Creation Failed] {err} ({type(err).__name__})")
        if "assistant" in locals():
            _backout(assistant_crud, assistant.id)
        try:
            collection = collection_crud.read_one(UUID(payload.key))
            collection.status = CollectionStatus.failed
            collection.updated_at = now()
            collection_crud._update(collection)
        except Exception as suberr:
            logging.warning(f"[Collection Status Update Failed] {suberr}")
        callback.fail(str(err))


@router.post(
    "/create",
    description=load_description("collections/create.md"),
)
def create_collection(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: CreationRequest,
    background_tasks: BackgroundTasks,
):
    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload("processing", route)
    logger.info(
        f"[create_collection] Initiating collection creation | {{'user_id': '{current_user.id}', 'payload_key': '{payload.key}'}}"
    )

    collection = Collection(
        id=UUID(payload.key),
        owner_id=current_user.id,
        organization_id=current_user.organization_id,
        project_id=current_user.project_id,
        status=CollectionStatus.processing,
    )

    collection_crud = CollectionCrud(session, current_user.id)
    collection_crud.create(collection)

    # 2. Launch background task
    background_tasks.add_task(
        do_create_collection,
        session,
        current_user,
        request,
        payload,
    )

    logger.info(
        f"[create_collection] Background task for collection creation scheduled | "
        f"{{'collection_id': '{collection.id}'}}"
    )
    return APIResponse.success_response(data=None, metadata=asdict(payload))


def do_delete_collection(
    session: SessionDep,
    current_user: CurrentUser,
    request: DeletionRequest,
    payload: ResponsePayload,
):
    logger.info(
        f"[do_delete_collection] Starting collection deletion | {{'user_id': '{current_user.id}', 'collection_id': '{request.collection_id}'}}"
    )
    if request.callback_url is None:
        callback = SilentCallback(payload)
    else:
        callback = WebHookCallback(request.callback_url, payload)

    collection_crud = CollectionCrud(session, current_user.id)
    try:
        logger.info(
            f"[do_delete_collection] Reading collection | {{'collection_id': '{request.collection_id}'}}"
        )
        collection = collection_crud.read_one(request.collection_id)
        assistant = OpenAIAssistantCrud()
        logger.info(
            f"[do_delete_collection] Deleting collection | {{'collection_id': '{collection.id}'}}"
        )
        data = collection_crud.delete(collection, assistant)
        logger.info(
            f"[do_delete_collection] Collection deleted successfully | {{'collection_id': '{collection.id}'}}"
        )
        callback.success(data.model_dump(mode="json"))
    except (ValueError, PermissionError, SQLAlchemyError) as err:
        logger.warning(
            f"[do_delete_collection] Failed to delete collection | {{'collection_id': '{request.collection_id}', 'error': '{str(err)}'}}"
        )
        callback.fail(str(err))
    except Exception as err:
        logger.error(
            f"[do_delete_collection] Unexpected error during deletion | {{'collection_id': '{request.collection_id}', 'error': '{str(err)}', 'error_type': '{type(err).__name__}'}}"
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
    logger.info(
        f"[delete_collection] Initiating collection deletion | {{'user_id': '{current_user.id}', 'collection_id': '{request.collection_id}'}}"
    )

    background_tasks.add_task(
        do_delete_collection,
        session,
        current_user,
        request,
        payload,
    )

    logger.info(
        f"[delete_collection] Background task for deletion scheduled | "
        f"{{'collection_id': '{request.collection_id}', 'payload_key': '{payload.key}'}}"
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
    logger.info(
        f"[collection_info] Retrieving collection info | {{'user_id': '{current_user.id}', 'collection_id': '{collection_id}'}}"
    )
    collection_crud = CollectionCrud(session, current_user.id)
    data = collection_crud.read_one(collection_id)
    logger.info(
        f"[collection_info] Collection retrieved successfully | {{'collection_id': '{collection_id}'}}"
    )
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
    logger.info(
        f"[list_collections] Listing collections | {{'user_id': '{current_user.id}'}}"
    )
    collection_crud = CollectionCrud(session, current_user.id)
    data = collection_crud.read_all()
    logger.info(
        f"[list_collections] Collections retrieved successfully | {{'collection_count': {len(data)}}}"
    )
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
    logger.info(
        f"[collection_documents] Retrieving documents for collection | {{'user_id': '{current_user.id}', 'collection_id': '{collection_id}', 'skip': {skip}, 'limit': {limit}}}"
    )
    collection_crud = CollectionCrud(session, current_user.id)
    document_collection_crud = DocumentCollectionCrud(session)
    collection = collection_crud.read_one(collection_id)
    data = document_collection_crud.read(collection, skip, limit)
    logger.info(
        f"[collection_documents] Documents retrieved successfully | {{'collection_id': '{collection_id}', 'document_count': {len(data)}}}"
    )
    return APIResponse.success_response(data)
