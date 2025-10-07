from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Path as FastPath

from app.api.deps import CurrentUserOrgProject, SessionDep
from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.models import DocTransformationJob, DocTransformationJobs
from app.utils import APIResponse

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
    job_ids: list[UUID] = Query(
        description="List of transformation job IDs", min=1, max_length=100
    ),
):
    crud = DocTransformationJobCrud(session, project_id=current_user.project_id)
    jobs = crud.read_each(set(job_ids))
    jobs_not_found = set(job_ids) - {job.id for job in jobs}
    return APIResponse.success_response(
        DocTransformationJobs(jobs=jobs, jobs_not_found=list(jobs_not_found))
    )
