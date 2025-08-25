import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Path as FastPath
from app.models import DocTransformationJob, DocTransformationJobs
from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.utils import APIResponse
from app.api.deps import SessionDep, CurrentUserOrgProject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents/transformations", tags=["doc_transformation_job"])


@router.get(
    "/{job_id}",
    description="Get the status and details of a document transformation job.",
    response_model=APIResponse[DocTransformationJob],
)
def get_transformation_job(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    job_id: UUID = FastPath(description="Transformation job ID"),
):
    crud = DocTransformationJobCrud(session, current_user.project_id)
    job = crud.read_one(job_id)
    return APIResponse.success_response(job)


@router.get(
    "/",
    description="Get the status and details of multiple document transformation jobs by IDs.",
    response_model=APIResponse[DocTransformationJobs],
)
def get_multiple_transformation_jobs(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    job_ids: str = Query(..., description="Comma-separated list of transformation job IDs"),
):
    job_id_list = []
    invalid_ids = []
    for jid in job_ids.split(","):
        jid = jid.strip()
        if not jid:
            continue
        try:
            job_id_list.append(UUID(jid))
        except ValueError:
            invalid_ids.append(jid)

    if invalid_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid UUID(s) provided: {', '.join(invalid_ids)}",
        )

    crud = DocTransformationJobCrud(session, project_id=current_user.project_id)
    jobs = crud.read_each(set(job_id_list))
    jobs_not_found = set(job_id_list) - {job.id for job in jobs}
    return APIResponse.success_response(DocTransformationJobs(jobs=jobs, jobs_not_found=jobs_not_found))