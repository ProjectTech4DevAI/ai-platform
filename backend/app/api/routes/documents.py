import logging
from uuid import UUID, uuid4
from typing import List
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Query
from fastapi import Path as FastPath

from app.crud import DocumentCrud, CollectionCrud
from app.models import Document
from app.utils import APIResponse, load_description
from app.api.deps import CurrentUser, SessionDep
from app.core.cloud import AmazonCloudStorage
from app.crud.rag import OpenAIAssistantCrud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "/list",
    description=load_description("documents/list.md"),
    response_model=APIResponse[List[Document]],
)
def list_docs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    logger.info(
        f"[list_docs] Listing documents | {{'user_id': '{current_user.id}', 'skip': {skip}, 'limit': {limit}}}"
    )
    crud = DocumentCrud(session, current_user.id)
    data = crud.read_many(skip, limit)
    logger.info(
        f"[list_docs] Documents retrieved successfully | {{'user_id': '{current_user.id}', 'document_count': {len(data)}}}"
    )
    return APIResponse.success_response(data)


@router.post(
    "/upload",
    description=load_description("documents/upload.md"),
    response_model=APIResponse[Document],
)
def upload_doc(
    session: SessionDep,
    current_user: CurrentUser,
    src: UploadFile = File(...),
):
    logger.info(
        f"[upload_doc] Starting document upload | {{'user_id': '{current_user.id}', 'filename': '{src.filename}'}}"
    )
    storage = AmazonCloudStorage(current_user)
    document_id = uuid4()
    logger.info(
        f"[upload_doc] Uploading to cloud storage | {{'user_id': '{current_user.id}', 'document_id': '{document_id}'}}"
    )
    object_store_url = storage.put(src, Path(str(document_id)))

    crud = DocumentCrud(session, current_user.id)
    document = Document(
        id=document_id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )
    logger.info(
        f"[upload_doc] Updating document in DB | {{'user_id': '{current_user.id}', 'document_id': '{document_id}'}}"
    )
    data = crud.update(document)
    logger.info(
        f"[upload_doc] Document uploaded successfully | {{'user_id': '{current_user.id}', 'document_id': '{document_id}'}}"
    )
    return APIResponse.success_response(data)


@router.get(
    "/remove/{doc_id}",
    description=load_description("documents/delete.md"),
    response_model=APIResponse[Document],
)
def remove_doc(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID = FastPath(description="Document to delete"),
):
    logger.info(
        f"[remove_doc] Starting document deletion | {{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )
    a_crud = OpenAIAssistantCrud()
    d_crud = DocumentCrud(session, current_user.id)
    c_crud = CollectionCrud(session, current_user.id)

    logger.info(
        f"[remove_doc] Deleting document from DB | {{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )
    document = d_crud.delete(doc_id)
    logger.info(
        f"[remove_doc] Deleting document from collection | {{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )
    data = c_crud.delete(document, a_crud)
    logger.info(
        f"[remove_doc] Document deleted successfully | {{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )
    return APIResponse.success_response(data)


@router.delete(
    "/remove/{doc_id}/permanent",
    description=load_description("documents/permanent_delete.md"),
    response_model=APIResponse[Document],
)
def permanent_delete_doc(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID = FastPath(description="Document to permanently delete"),
):
    logger.info(
        f"[permanent_delete_doc] Initiating permanent deletion | "
        f"{{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )

    a_crud = OpenAIAssistantCrud()
    d_crud = DocumentCrud(session, current_user.id)
    c_crud = CollectionCrud(session, current_user.id)
    storage = AmazonCloudStorage(current_user)

    document = d_crud.read_one(doc_id)

    logger.info(
        f"[permanent_delete_doc] Removing document from collection and assistant | "
        f"{{'document_id': '{doc_id}'}}"
    )
    c_crud.delete(document, a_crud)

    logger.info(
        f"[permanent_delete_doc] Deleting document from object storage | "
        f"{{'object_store_url': '{document.object_store_url}'}}"
    )
    storage.delete(document.object_store_url)
    d_crud.delete(doc_id)

    logger.info(
        f"[permanent_delete_doc] Document permanently deleted from Cloud and soft deleted from DB | "
        f"{{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )
    return APIResponse.success_response(document)


@router.get(
    "/info/{doc_id}",
    description=load_description("documents/info.md"),
    response_model=APIResponse[Document],
)
def doc_info(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID = FastPath(description="Document to retrieve"),
):
    logger.info(
        f"[doc_info] Retrieving document info | {{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )
    crud = DocumentCrud(session, current_user.id)
    data = crud.read_one(doc_id)
    logger.info(
        f"[doc_info] Document retrieved successfully | {{'user_id': '{current_user.id}', 'document_id': '{doc_id}'}}"
    )
    return APIResponse.success_response(data)
