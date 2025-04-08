import warnings
from uuid import UUID, uuid4
from typing import List

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

# from sqlalchemy.exc import NoResultFound, MultipleResultsFound, SQLAlchemyError

# from app.crud import DocumentCrud
# from app.models import Document
from app.utils import APIResponse
from app.api.deps import CurrentUser, SessionDep
from app.core.util import raise_from_unknown

# from app.core.cloud import AmazonCloudStorage, CloudStorageError

router = APIRouter(prefix="/collections", tags=["collections"])


def fields(cls: BaseModel):
    yield from cls.__fields__.keys()


class UserDocuments(BaseModel):
    documents: list
    batch_size: int = 1


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
    while True:
        view = request.document_ids[start:stop]
        if not view:
            break
        docs = d_crud.collect(view)
        files = [storage.stream(x.object_store_url) for x in docs]
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=files,
        )
        if file_batch.file_counts.completed != file_batch.file_counts.total:
            # TODO:
            #   1. find erroneous document,
            #   2. remove previously allocated resources

            detail = "Vector store error"  # TODO: update with bad docs
            raise HTTPException(status_code=507, detail=detail)

        start = stop
        stop += batch_size

    #
    # Create the assistant
    #

    kwargs = {x: getattr(request, x) for x in fields(AssistantOptions)}
    assistant = self.client.beta.assistants.create(
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
        llm_service=request.model,
        llm_service_id=assistant.id,
    )

    return c_crud.create(collection)
