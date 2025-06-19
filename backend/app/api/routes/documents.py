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
    crud = DocumentCrud(session, current_user.id)
    data = crud.read_many(skip, limit)
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
    storage = AmazonCloudStorage(current_user)
    document_id = uuid4()
    object_store_url = storage.put(src, Path(str(document_id)))

    crud = DocumentCrud(session, current_user.id)
    document = Document(
        id=document_id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )
    data = crud.update(document)
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
    a_crud = OpenAIAssistantCrud()
    d_crud = DocumentCrud(session, current_user.id)
    c_crud = CollectionCrud(session, current_user.id)

    document = d_crud.delete(doc_id)
    data = c_crud.delete(document, a_crud)
    return APIResponse.success_response(data)


@router.delete(
    "remove/{doc_id}/permanent",
    description=load_description("documents/permanent_delete.md"),
    response_model=APIResponse[Document],
)
def permanent_delete_doc(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID = FastPath(description="Document to permanently delete"),
):
    a_crud = OpenAIAssistantCrud()
    d_crud = DocumentCrud(session, current_user.id)
    c_crud = CollectionCrud(session, current_user.id)
    storage = AmazonCloudStorage(current_user)

    document = d_crud.read_one(doc_id)

    c_crud.delete(document, a_crud)
    storage.delete(document.object_store_url)
    d_crud.hard_delete(doc_id)

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
    crud = DocumentCrud(session, current_user.id)
    data = crud.read_one(doc_id)
    return APIResponse.success_response(data)
