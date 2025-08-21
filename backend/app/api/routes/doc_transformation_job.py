import logging
from uuid import UUID
from fastapi import APIRouter
from fastapi import Path as FastPath
from fastapi import Query
from typing import List
from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.utils import APIResponse
from app.api.deps import SessionDep, CurrentUser
from app.core.cloud import AmazonCloudStorage
from app.crud import DocumentCrud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents/transformations", tags=["doc_transformation_job"])

@router.get(
    "/{job_id}",
    description="Get the status and details of a document transformation job.",
    response_model=APIResponse,
)
def get_transformation_job(
    session: SessionDep,
    current_user: CurrentUser,
    job_id: UUID = FastPath(description="Transformation job ID"),
):
    crud = DocTransformationJobCrud(session)
    job = crud.read_one(job_id)

    # Get signed S3 URL for the transformed document if available
    transformed_document_id = getattr(job, "transformed_document_id", None)
    signed_url = None
    if transformed_document_id:
        doc_crud = DocumentCrud(session, current_user.id)
        transformed_doc = doc_crud.read_one(transformed_document_id)
        storage = AmazonCloudStorage(current_user)
        signed_url = storage.get_signed_url(transformed_doc.object_store_url)
    job_dict = job.model_dump() if hasattr(job, "model_dump") else dict(job)
    job_dict["transformed_document_signed_url"] = signed_url

    return APIResponse.success_response(job_dict)

@router.get(
    "/",
    description="Get the status and details of multiple document transformation jobs by IDs.",
    response_model=APIResponse,
)
def get_multiple_transformation_jobs(
    session: SessionDep,
    current_user: CurrentUser,
    job_ids: str = Query(..., description="Comma-separated list of transformation job IDs"),
):
    crud = DocTransformationJobCrud(session)
    try:
        job_id_list: List[UUID] = [UUID(jid.strip()) for jid in job_ids.split(",") if jid.strip()]
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid job_ids format. Must be comma-separated UUIDs.")
    jobs = [crud.read_one(job_id) for job_id in job_id_list]
    return APIResponse.success_response(jobs)
