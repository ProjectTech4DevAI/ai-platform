import warnings
from uuid import UUID, uuid4
from typing import List

from openai import OpenAI
from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

# from sqlalchemy.exc import NoResultFound, MultipleResultsFound, SQLAlchemyError

from app.crud import DocumentCrud, CollectionCrud, DocumentCollectionCrud
from app.models import Document, Collection
from app.utils import APIResponse
from app.api.deps import CurrentUser, SessionDep
from app.core.util import raise_from_unknown

# from app.core.cloud import AmazonCloudStorage, CloudStorageError

router = APIRouter(prefix="/collections", tags=["collections"])


def fields(cls: BaseModel):
    yield from cls.__fields__.keys()


def vs_ls(vector_store_id: str, client: OpenAI):
    kwargs = {}
    while True:
        page = client.beta.vector_stores.files.list(
            vector_store_id=vector_store_id,
            **kwargs,
        )
        yield from page
        if not page.has_more:
            break
        kwargs["after"] = page.last_id


class UserDocuments(BaseModel):
    documents: list
    batch_size: int = 1


# Fields to be passed along to OpenAI. They must be a subset of
# parameters accepted by the OpenAI.clien.beta.assistants.create API.
class AssistantOptions(BaseModel):
    model: str
    instructions: str
    temperature: float = 1e-6


class CreationRequest(UserDocuments, AssistantOptions):
    pass


@router.post("/create", response_model=APIResponse[Collection])
def create_collection(
    session: SessionDep,
    current_user: CurrentUser,
    request: CreationRequest,
    background_tasks: BackgroundTasks,
):
    d_crud = DocumentCrud(session, current_user.id)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    storage = AmazonCloudStorage()

    #
    # Create the vector store
    #

    vector_store = client.beta.vector_stores.create()

    (start, stop) = (0, request.batch_size)
    documents = []
    while True:
        view = request.document_ids[start:stop]
        if not view:
            break
        docs = {x.object_store_url: x for x in d_crud.collect(view)}
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=list(map(storage.stream, docs)),
        )
        if file_batch.file_counts.completed != file_batch.file_counts.total:
            for i in vs_ls(vector_store.id, client):
                if i.last_error is None:
                    object_store_url = client.files.retrieve(i.id)
                    docs.pop(object_store_url)
                client.files.delete(i.id)
            client.beta.vector_stores.delete(vector_store.id)

            detail = json.dumps(
                {
                    "error": "OpenAI document processing error",
                    "documents": [x.model_dump() for x in docs.values()],
                }
            )
            raise HTTPException(status_code=507, detail=detail)

        start = stop
        stop += request.batch_size
        documents.extend(docs.values())

    #
    # Create the assistant
    #

    kwargs = {x: getattr(request, x) for x in fields(AssistantOptions)}
    assistant = client.beta.assistants.create(
        tools=[
            {
                "type": "file_search",
            }
        ],
        tool_resources={
            "file_search": {
                "vector_store_ids": [
                    vector_store.id,
                ],
            },
        },
        **kwargs,
    )

    #
    # Store the results
    #

    c_crud = CollectionCrud()
    collection = Collection(
        llm_service_id=assistant.id,
        llm_service_name=request.model,
    )
    c_crud.create(collection)

    dc_crud = DocumentCollectionCrud()
    dc_crud.update(collection, documents)

    return APIResponse.success_response(collection)
