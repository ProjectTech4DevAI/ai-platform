from uuid import UUID
import logging

from fastapi import APIRouter, Query, Path

from app.api.deps import CurrentUserOrgProject, SessionDep
from app.crud import DocTransformationJobCrud, DocumentCrud
from app.models import (
    DocTransformationJobPublic,
    DocTransformationJobsPublic,
)
from app.utils import APIResponse, load_description
from app.services.documents.helpers import build_job_schema, build_job_schemas
from app.core.cloud import get_cloud_storage


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents/transformation", tags=["Documents"])


@router.get(
    "/{job_id}",
    description=load_description("documents/job_info.md"),
    response_model=APIResponse[DocTransformationJobPublic],
)
def get_transformation_job(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    job_id: UUID = Path(..., description="Transformation job ID"),
    include_url: bool = Query(
        False, description="Include a signed URL for the transformed document"
    ),
):
    job_crud = DocTransformationJobCrud(session, current_user.project_id)
    doc_crud = DocumentCrud(session, current_user.project_id)

    job = job_crud.read_one(job_id)
    storage = (
        get_cloud_storage(session=session, project_id=current_user.project_id)
        if include_url
        else None
    )

    job_schema = build_job_schema(
        job=job,
        doc_crud=doc_crud,
        include_url=include_url,
        storage=storage,
    )
    return APIResponse.success_response(job_schema)


@router.get(
    "/",
    description=load_description("documents/job_list.md"),
    response_model=APIResponse[DocTransformationJobsPublic],
)
def get_multiple_transformation_jobs(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    job_ids: list[UUID] = Query(
        ...,
        description="List of transformation job IDs",
        min_items=1,
        max_items=100,
    ),
    include_url: bool = Query(
        False, description="Include a signed URL for each transformed document"
    ),
):
    job_crud = DocTransformationJobCrud(session, project_id=current_user.project_id)
    doc_crud = DocumentCrud(session, project_id=current_user.project_id)

    jobs = job_crud.read_each(set(job_ids))
    jobs_found_ids = {job.id for job in jobs}
    jobs_not_found = set(job_ids) - jobs_found_ids

    storage = (
        get_cloud_storage(session=session, project_id=current_user.project_id)
        if include_url
        else None
    )

    job_schemas = build_job_schemas(
        jobs=jobs,
        doc_crud=doc_crud,
        include_url=include_url,
        storage=storage,
    )

    return APIResponse.success_response(
        DocTransformationJobsPublic(
            jobs=job_schemas,
            jobs_not_found=list(jobs_not_found),
        )
    )
