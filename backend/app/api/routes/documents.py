import logging
from uuid import UUID, uuid4
from typing import List
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Query, HTTPException
from fastapi import Path as FastPath

from app.crud import DocumentCrud, CollectionCrud, get_project_by_id
from app.models import Document, DocumentPublic, Message
from app.utils import APIResponse, load_description, get_openai_client
from app.api.deps import CurrentUser, SessionDep, CurrentUserOrgProject
from app.core.cloud import get_cloud_storage
from app.crud.rag import OpenAIAssistantCrud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "/list",
    description=load_description("documents/list.md"),
    response_model=APIResponse[List[DocumentPublic]],
)
def list_docs(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    crud = DocumentCrud(session, current_user.project_id)
    data = crud.read_many(skip, limit)
    return APIResponse.success_response(data)


@router.post(
    "/upload",
    description=load_description("documents/upload.md"),
    response_model=APIResponse[DocumentPublic],
)
def upload_doc(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    src: UploadFile = File(...),
):
    storage = get_cloud_storage(session=session, project_id=current_user.project_id)
    document_id = uuid4()

    object_store_url = storage.put(src, Path(str(document_id)))

    crud = DocumentCrud(session, current_user.project_id)
    document = Document(
        id=document_id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )
    data = crud.update(document)
    return APIResponse.success_response(data)


@router.delete(
    "/remove/{doc_id}",
    description=load_description("documents/delete.md"),
    response_model=APIResponse[Message],
)
def remove_doc(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    doc_id: UUID = FastPath(description="Document to delete"),
):
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )

    a_crud = OpenAIAssistantCrud(client)
    d_crud = DocumentCrud(session, current_user.project_id)
    c_crud = CollectionCrud(session, current_user.id)

    document = d_crud.delete(doc_id)
    data = c_crud.delete(document, a_crud)

    return APIResponse.success_response(
        Message(message="Document Deleted Successfully")
    )


@router.delete(
    "/remove/{doc_id}/permanent",
    description=load_description("documents/permanent_delete.md"),
    response_model=APIResponse[Message],
)
def permanent_delete_doc(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    doc_id: UUID = FastPath(description="Document to permanently delete"),
):
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )
    project = get_project_by_id(session=session, project_id=current_user.project_id)
    a_crud = OpenAIAssistantCrud(client)
    d_crud = DocumentCrud(session, current_user.project_id)
    c_crud = CollectionCrud(session, current_user.id)
    storage = get_cloud_storage(session=session, project_id=current_user.project_id)

    document = d_crud.read_one(doc_id)

    c_crud.delete(document, a_crud)

    storage.delete(document.object_store_url)
    d_crud.delete(doc_id)

    return APIResponse.success_response(
        Message(message="Document Permanently Deleted Successfully")
    )


@router.get(
    "/info/{doc_id}",
    description=load_description("documents/info.md"),
    response_model=APIResponse[DocumentPublic],
)
def doc_info(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    doc_id: UUID = FastPath(description="Document to retrieve"),
    include_url: bool = Query(
        False, description="Include a signed URL to access the document"
    ),
):
    crud = DocumentCrud(session, current_user.project_id)
    document = crud.read_one(doc_id)

    doc_schema = DocumentPublic.model_validate(document, from_attributes=True)
    if include_url:
        storage = get_cloud_storage(session=session, project_id=current_user.project_id)
        doc_schema.signed_url = storage.get_signed_url(document.object_store_url)

    return APIResponse.success_response(doc_schema)
