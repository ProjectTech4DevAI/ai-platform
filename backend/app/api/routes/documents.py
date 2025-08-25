import logging
from uuid import UUID, uuid4
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Query, Form, BackgroundTasks, HTTPException
from fastapi import Path as FastPath
from fastapi.responses import JSONResponse
from fastapi import HTTPException

from app.crud import DocumentCrud, CollectionCrud, get_project_by_id
from app.models import Document, DocumentPublic, Message, DocumentUploadResponse, TransformationJobInfo
from app.utils import APIResponse, load_description, get_openai_client
from app.api.deps import CurrentUser, SessionDep, CurrentUserOrgProject
from app.core.cloud import AmazonCloudStorage
from app.crud.rag import OpenAIAssistantCrud
from app.core.doctransform import service as transformation_service
from app.core.doctransform.registry import (
    get_file_format, 
    is_transformation_supported, 
    get_available_transformers,
    resolve_transformer
)

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
    response_model=APIResponse[DocumentUploadResponse],
)
async def upload_doc(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    src: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    target_format: str | None = Form(
        None,
        description="Desired output format for the uploaded document (e.g., pdf, docx, txt). "
    ),
    transformer: str | None = Form(
        None,
        description="Name of the transformer to apply when converting. "
    ),
):
    # Determine source file format
    try:
        source_format = get_file_format(src.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # validate if transformation is possible or not
    if target_format:
        if not is_transformation_supported(source_format, target_format):
            raise HTTPException(
                status_code=400,
                detail=f"Transformation from {source_format} to {target_format} is not supported"
            )

        # Resolve the transformer to use
        if not transformer:
            transformer = "default"
        try:
            actual_transformer = resolve_transformer(source_format, target_format, transformer)
        except ValueError as e:
            available_transformers = get_available_transformers(source_format, target_format)
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}. Available transformers: {list(available_transformers.keys())}"
            )
        
    storage = AmazonCloudStorage(current_user.project_id)
    document_id = uuid4()
    project = get_project_by_id(session=session, project_id=current_user.project_id)
    if project is None:
        raise HTTPException(404, "Project not found")

    key = Path(str(project.storage_path), str(document_id))
    object_store_url = storage.put(src, key)

    crud = DocumentCrud(session, current_user.project_id)
    document = Document(
        id=document_id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )
    source_document = crud.update(document)


    job_info: TransformationJobInfo | None = None
    if target_format and actual_transformer:
        job_id = transformation_service.start_job(
            db=session,
            current_user=current_user,
            source_document_id=source_document.id,
            transformer_name=actual_transformer,
            target_format=target_format,
            background_tasks=background_tasks,
        )
        job_info = TransformationJobInfo(
            message=f"Document accepted for transformation from {source_format} to {target_format}.",
            job_id=str(job_id),
            source_format=source_format,
            target_format=target_format,
            transformer=actual_transformer,
            status_check_url=f"/documents/transformations/{job_id}"
        )

    document_schema = DocumentPublic.model_validate(source_document, from_attributes=True)
    response = DocumentUploadResponse(
        **document_schema.model_dump(),
        transformation_job=job_info
    )

    return APIResponse.success_response(response)


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

    a_crud = OpenAIAssistantCrud(client)
    d_crud = DocumentCrud(session, current_user.project_id)
    c_crud = CollectionCrud(session, current_user.id)
    storage = AmazonCloudStorage(current_user.project_id)

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
        storage = AmazonCloudStorage(current_user.project_id)
        doc_schema.signed_url = storage.get_signed_url(document.object_store_url)

    return APIResponse.success_response(doc_schema)
