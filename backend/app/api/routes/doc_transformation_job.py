from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, Query, Path

from app.api.deps import CurrentUserOrgProject, SessionDep
from app.crud import DocTransformationJobCrud, DocumentCrud
from app.models import (
    DocTransformationJobPublic,
    DocTransformationJobsPublic,
    TransformedDocumentPublic,
)
from app.utils import APIResponse
from app.core.cloud import get_cloud_storage


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["doc_transformation_job"])


@router.get(
    "/transformation/{job_id}",
    description="Get the status and details of a document transformation job.",
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

    transformed_doc_schema = None
    if getattr(job, "transformed_document_id", None):
        document = doc_crud.read_one(job.transformed_document_id)
        transformed_doc_schema = TransformedDocumentPublic.model_validate(
            document, from_attributes=True
        )

        if include_url:
            storage = get_cloud_storage(
                session=session, project_id=current_user.project_id
            )
            transformed_doc_schema.signed_url = storage.get_signed_url(
                document.object_store_url
            )

    job_schema = DocTransformationJobPublic.model_validate(job, from_attributes=True)
    job_schema = job_schema.model_copy(
        update={"transformed_document": transformed_doc_schema}
    )

    return APIResponse.success_response(job_schema)


@router.get(
    "/transformation/",
    description="Get the status and details of multiple document transformation jobs by IDs.",
    response_model=APIResponse[DocTransformationJobsPublic],
)
def get_multiple_transformation_jobs(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    job_ids: list[UUID] = Query(
        description="List of transformation job IDs", min=1, max_length=100
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

    storage = None
    if include_url:
        storage = get_cloud_storage(session=session, project_id=current_user.project_id)

    job_schemas: list[DocTransformationJobPublic] = []

    for job in jobs:
        transformed_doc_schema = None

        if getattr(job, "transformed_document_id", None):
            document = doc_crud.read_one(job.transformed_document_id)
            transformed_doc_schema = TransformedDocumentPublic.model_validate(
                document, from_attributes=True
            )

            if include_url and storage:
                transformed_doc_schema.signed_url = storage.get_signed_url(
                    document.object_store_url
                )

        job_schema = DocTransformationJobPublic.model_validate(
            job, from_attributes=True
        )
        job_schema = job_schema.model_copy(
            update={"transformed_document": transformed_doc_schema}
        )
        job_schemas.append(job_schema)

    return APIResponse.success_response(
        DocTransformationJobsPublic(
            jobs=job_schemas,
            jobs_not_found=list(jobs_not_found),
        )
    )
