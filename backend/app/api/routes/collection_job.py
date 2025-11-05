import logging
from uuid import UUID

from fastapi import APIRouter
from fastapi import Path as FastPath


from app.api.deps import SessionDep, CurrentUserOrgProject
from app.crud import (
    CollectionCrud,
    CollectionJobCrud,
)
from app.models import (
    CollectionJobStatus,
    CollectionIDPublic,
    CollectionActionType,
    CollectionJobPublic,
)
from app.models.collection import CollectionPublic
from app.utils import APIResponse, load_description
from app.services.collections.helpers import extract_error_message


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


@router.get(
    "/jobs/{job_id}",
    description=load_description("collections/job_info.md"),
    response_model=APIResponse[CollectionJobPublic],
    response_model_exclude={"data": {"error_message"}},
)
def collection_job_info(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    job_id: UUID = FastPath(description="Collection job to retrieve"),
):
    collection_job_crud = CollectionJobCrud(session, current_user.project_id)
    collection_job = collection_job_crud.read_one(job_id)

    job_out = CollectionJobPublic.model_validate(collection_job)

    if collection_job.collection_id:
        if (
            collection_job.action_type == CollectionActionType.CREATE
            and collection_job.status == CollectionJobStatus.SUCCESSFUL
        ):
            collection_crud = CollectionCrud(session, current_user.project_id)
            collection = collection_crud.read_one(collection_job.collection_id)
            job_out.collection = CollectionPublic.model_validate(collection)

        elif collection_job.action_type == CollectionActionType.DELETE:
            job_out.collection = CollectionIDPublic(id=collection_job.collection_id)

    if collection_job.status == CollectionJobStatus.FAILED:
        raw_error = getattr(collection_job, "error_message", None)
        error_message = extract_error_message(raw_error)

        return APIResponse.failure_response(
            error=error_message,
            data=job_out,
        )

    return APIResponse.success_response(data=job_out)
