import logging
from pathlib import Path
from typing import Union
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi import Path as FastPath

from app.api.deps import CurrentUserOrgProject, SessionDep
from app.core.cloud import get_cloud_storage
from app.services.doctransform import job as transformation_job
from app.services.doctransform.registry import (
    get_available_transformers,
    get_file_format,
    is_transformation_supported,
    resolve_transformer,
)
from app.crud import CollectionCrud, DocumentCrud, DocTransformationJobCrud
from app.crud.rag import OpenAIAssistantCrud, OpenAIVectorStoreCrud
from app.models import (
    Document,
    DocumentPublic,
    TransformedDocumentPublic,
    DocumentUploadResponse,
    DocTransformJobCreate,
    Message,
    TransformationStatus,
    TransformationJobInfo,
)
from app.services.collections.helpers import pick_service_for_documennt
from app.utils import APIResponse, get_openai_client, load_description


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "/",
    description=load_description("documents/list.md"),
    response_model=APIResponse[list[DocumentPublic]],
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
    "/",
    description=load_description("documents/upload.md"),
    response_model=APIResponse[DocumentUploadResponse],
)
async def upload_doc(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    src: UploadFile = File(...),
    target_format: str
    | None = Form(
        None,
        description="Desired output format for the uploaded document (e.g., pdf, docx, txt). ",
    ),
    transformer: str
    | None = Form(
        None, description="Name of the transformer to apply when converting. "
    ),
    callback_url: str | None = Form("URL to call to report endpoint status"),
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
                detail=f"Transformation from {source_format} to {target_format} is not supported",
            )

        # Resolve the transformer to use
        if not transformer:
            transformer = "default"
        try:
            actual_transformer = resolve_transformer(
                source_format, target_format, transformer
            )
        except ValueError as e:
            available_transformers = get_available_transformers(
                source_format, target_format
            )
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}. Available transformers: {list(available_transformers.keys())}",
            )

    storage = get_cloud_storage(session=session, project_id=current_user.project_id)
    document_id = uuid4()

    object_store_url = storage.put(src, Path(str(document_id)))

    crud = DocumentCrud(session, current_user.project_id)
    document = Document(
        id=document_id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )
    source_document = crud.update(document)

    job_info: TransformationJobInfo | None = None
    if target_format and actual_transformer:
        job_crud = DocTransformationJobCrud(session, current_user.project_id)
        job = job_crud.create(
            DocTransformJobCreate(source_document_id=source_document.id)
        )

        transformation_job_id = transformation_job.start_job(
            db=session,
            job_id=job.id,
            current_user=current_user,
            transformer_name=actual_transformer,
            target_format=target_format,
            callback_url=callback_url,
        )
        job_info = TransformationJobInfo(
            message=f"Document accepted for transformation from {source_format} to {target_format}.",
            job_id=str(transformation_job_id),
            status=TransformationStatus.PENDING,
            transformer=actual_transformer,
            status_check_url=f"/documents/transformations/{transformation_job_id}",
        )

    document_schema = DocumentPublic.model_validate(
        source_document, from_attributes=True
    )
    document_schema.signed_url = storage.get_signed_url(
        source_document.object_store_url
    )
    response = DocumentUploadResponse(
        **document_schema.model_dump(), transformation_job=job_info
    )

    return APIResponse.success_response(response)


@router.delete(
    "/{doc_id}",
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
    v_crud = OpenAIVectorStoreCrud(client)
    d_crud = DocumentCrud(session, current_user.project_id)
    c_crud = CollectionCrud(session, current_user.project_id)
    document = d_crud.read_one(doc_id)

    remote = pick_service_for_documennt(
        session, doc_id, a_crud, v_crud
    )  # assistant crud or vector store crud
    c_crud.delete(document, remote)
    d_crud.delete(doc_id)

    return APIResponse.success_response(
        Message(message="Document Deleted Successfully")
    )


@router.delete(
    "/{doc_id}/permanent",
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
    v_crud = OpenAIVectorStoreCrud(client)
    d_crud = DocumentCrud(session, current_user.project_id)
    c_crud = CollectionCrud(session, current_user.project_id)
    storage = get_cloud_storage(session=session, project_id=current_user.project_id)

    document = d_crud.read_one(doc_id)

    remote = pick_service_for_documennt(
        session, doc_id, a_crud, v_crud
    )  # assistant crud or vector store crud
    c_crud.delete(document, remote)

    storage.delete(document.object_store_url)
    d_crud.delete(doc_id)

    return APIResponse.success_response(
        Message(message="Document permanently deleted successfully")
    )


@router.get(
    "/{doc_id}",
    description=load_description("documents/info.md"),
    response_model=APIResponse[Union[DocumentPublic, TransformedDocumentPublic]],
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

    if document.source_document_id is None:
        doc_schema = DocumentPublic.model_validate(document, from_attributes=True)

    else:
        doc_schema = TransformedDocumentPublic.model_validate(
            document, from_attributes=True
        )

    if include_url:
        storage = get_cloud_storage(session=session, project_id=current_user.project_id)
        doc_schema.signed_url = storage.get_signed_url(document.object_store_url)

    return APIResponse.success_response(doc_schema)
