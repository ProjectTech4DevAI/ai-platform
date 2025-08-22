import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi import Path as FastPath
from fastapi import Query
from app.models import DocTransformationJob
from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.utils import APIResponse
from app.api.deps import SessionDep, CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents/transformations", tags=["doc_transformation_job"])

@router.get(
    "/{job_id}",
    description="Get the status and details of a document transformation job.",
    response_model=APIResponse[DocTransformationJob],
)
def get_transformation_job(
    session: SessionDep,
    current_user: CurrentUser,
    job_id: UUID = FastPath(description="Transformation job ID"),
):
    crud = DocTransformationJobCrud(session)
    job = crud.read_one(job_id)
    return APIResponse.success_response(job)

@router.get(
    "/",
    description="Get the status and details of multiple document transformation jobs by IDs.",
    response_model=APIResponse[list[DocTransformationJob]],
)
def get_multiple_transformation_jobs(
    session: SessionDep,
    current_user: CurrentUser,
    job_ids: str = Query(..., description="Comma-separated list of transformation job IDs"),
):
    crud = DocTransformationJobCrud(session)
    try:
        job_id_list: list[UUID] = [UUID(jid.strip()) for jid in job_ids.split(",") if jid.strip()]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job_ids format. Must be comma-separated UUIDs.")
    jobs = [crud.read_one(job_id) for job_id in job_id_list]
    return APIResponse.success_response(jobs)
