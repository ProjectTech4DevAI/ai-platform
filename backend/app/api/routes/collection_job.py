import logging
from uuid import UUID

from fastapi import APIRouter
from fastapi import Path as FastPath


from app.api.deps import SessionDep, CurrentUserOrgProject
from app.crud import (
    CollectionCrud,
    CollectionJobCrud,
)
from app.models import CollectionJobStatus, CollectionJobPublic, CollectionActionType
from app.models.collection import CollectionPublic
from app.utils import APIResponse, load_description
from app.services.collections.helpers import extract_error_message


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


@router.get(
    "/info/jobs/{job_id}",
    description=load_description("collections/job_info.md"),
    response_model=APIResponse[CollectionJobPublic],
)
def collection_job_info(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    job_id: UUID = FastPath(description="Collection job to retrieve"),
):
    collection_job_crud = CollectionJobCrud(session, current_user.project_id)
    collection_job = collection_job_crud.read_one(job_id)

    job_out = CollectionJobPublic.model_validate(collection_job)

    if (
        collection_job.status == CollectionJobStatus.SUCCESSFUL
        and collection_job.action_type == CollectionActionType.CREATE
        and collection_job.collection_id
    ):
        collection_crud = CollectionCrud(session, current_user.project_id)
        collection = collection_crud.read_one(collection_job.collection_id)
        job_out.collection = CollectionPublic.model_validate(collection)

    if collection_job.status == CollectionJobStatus.FAILED and job_out.error_message:
        job_out.error_message = extract_error_message(job_out.error_message)

    return APIResponse.success_response(data=job_out)
