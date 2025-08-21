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
    transformer: Optional[str] = Form(None),
):
    # Determine source file format
    try:
        source_format = get_file_format(src.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Upload the original document first
    storage = AmazonCloudStorage(current_user)
    document_id = uuid4()
    object_store_url = storage.put(src, Path(str(document_id)))
    crud = DocumentCrud(session, current_user.id)
    document = Document(
        id=document_id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )
    source_document = crud.update(document)

    # Generate signed S3 URL for the original document
    signed_url = storage.get_signed_url(str(object_store_url))

    # If no target format specified, return the uploaded document
    if not target_format:
        return APIResponse.success_response({
            "document": source_document,
            "signed_url": signed_url,
        })

    # Validate the requested transformation
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

    # Start the transformation job
    job_id = transformation_service.start_job(
        db=session,
        current_user=current_user,
        source_document_id=source_document.id,
        transformer_name=actual_transformer,
        target_format=target_format,
        background_tasks=background_tasks,
    )

    # Compose response with full document metadata and job info
    # response_data = {
    #     "message": f"Document accepted for transformation from {source_format} to {target_format}.",
    #     "original_document": APIResponse.success_response(source_document),
    #     "transformation_job_id": str(job_id),
    #     "source_format": source_format,
    #     "target_format": target_format,
    #     "transformer": actual_transformer,
    #     "status_check_url": f"/documents/transformations/{job_id}"
    # }

    response_data = {
        "message": f"Document accepted for transformation from {source_format} to {target_format}.",
        "original_document_id": str(source_document.id),
        "original_document_signed_url": signed_url,
        "transformation_job_id": str(job_id),
        "source_format": source_format,
        "target_format": target_format,
        "transformer": actual_transformer,
        "status_check_url": f"/documents/transformations/{job_id}"
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
