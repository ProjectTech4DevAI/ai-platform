import logging
from uuid import UUID, uuid4
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Query, Form, BackgroundTasks
from fastapi import Path as FastPath
from fastapi.responses import JSONResponse
from fastapi import HTTPException

from app.crud import DocumentCrud, CollectionCrud
from app.models import Document
from app.utils import APIResponse, load_description, get_openai_client
from app.api.deps import CurrentUser, SessionDep, CurrentUserOrgProject
from app.core.cloud import AmazonCloudStorage
from app.crud.rag import OpenAIAssistantCrud
from app.core.doctransform import service as transformation_service

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
    crud = DocumentCrud(session, current_user.id)
    data = crud.read_many(skip, limit)
    return APIResponse.success_response(data)


@router.post(
    "/upload",
    description=load_description("documents/upload.md"),
    response_model=APIResponse[Document],
)
async def upload_doc(
    session: SessionDep,
    current_user: CurrentUser,
    src: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    target_format: Optional[str] = Form(None),
    transformer: Optional[str] = Form("default"),
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
    # Use update to insert or update as per existing logic
    source_document = crud.update(document)

    if not target_format:
        return APIResponse.success_response(source_document)

    if target_format.lower() != "markdown":
        raise HTTPException(
            status_code=400,
            detail="Only 'markdown' target_format is supported at this time."
        )

    job_id = transformation_service.start_job(
        db=session,
        current_user=current_user,
        source_document_id=source_document.id,
        transformer_name=transformer,
        background_tasks=background_tasks,
    )

    # Compose response with full document metadata and job info
    response_data = {
        "message": "Document accepted for transformation.",
        "original_document": APIResponse.success_response(source_document).data,
        "transformation_job_id": str(job_id),
        "status_check_url": f"/api/v1/documents/transformations/{job_id}"
    }

    return JSONResponse(
        status_code=202,
        content=APIResponse.success_response(response_data).model_dump()
    )


@router.get(
    "/remove/{doc_id}",
    description=load_description("documents/delete.md"),
    response_model=APIResponse[Document],
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
    d_crud = DocumentCrud(session, current_user.id)
    c_crud = CollectionCrud(session, current_user.id)

    document = d_crud.delete(doc_id)
    data = c_crud.delete(document, a_crud)
    return APIResponse.success_response(data)


@router.delete(
    "/remove/{doc_id}/permanent",
    description=load_description("documents/permanent_delete.md"),
    response_model=APIResponse[Document],
)
def permanent_delete_doc(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    doc_id: UUID = FastPath(description="Document to permanently delete"),
):
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )

    a_crud = OpenAIAssistantCrud(client)
    d_crud = DocumentCrud(session, current_user.id)
    c_crud = CollectionCrud(session, current_user.id)
    storage = AmazonCloudStorage(current_user)

    document = d_crud.read_one(doc_id)

    c_crud.delete(document, a_crud)

    storage.delete(document.object_store_url)
    d_crud.delete(doc_id)

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
