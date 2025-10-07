import logging
from uuid import UUID
from typing import Union

from fastapi import APIRouter
from fastapi import Path as FastPath


from app.api.deps import SessionDep, CurrentUserOrgProject
from app.crud import (
    CollectionCrud,
    CollectionJobCrud,
)
from app.models import CollectionJobStatus, CollectionJobPublic
from app.models.collection import CollectionPublic
from app.utils import APIResponse, load_description
from app.services.collections.helpers import extract_error_message


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


@router.get(
    "/info/collection_job/{collection_job_id}",
    description=load_description("collections/job_info.md"),
    response_model=Union[
        APIResponse[CollectionPublic], APIResponse[CollectionJobPublic]
    ],
)
def collection_job_info(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    collection_job_id: UUID = FastPath(description="Collection job to retrieve"),
):
    collection_job_crud = CollectionJobCrud(session, current_user.project_id)
    collection_job = collection_job_crud.read_one(collection_job_id)

    if collection_job.status == CollectionJobStatus.SUCCESSFUL:
        collection_crud = CollectionCrud(session, current_user.project_id)
        collection = collection_crud.read_one(collection_job.collection_id)
        return APIResponse.success_response(
            data=CollectionPublic.model_validate(collection)
        )

    if collection_job.status == CollectionJobStatus.FAILED:
        err = getattr(collection_job, "error_message", None)
        if err:
            collection_job.error_message = extract_error_message(err)

        return APIResponse.success_response(
            data=CollectionJobPublic.model_validate(collection_job)
        )

    return APIResponse.success_response(
        data=CollectionJobPublic.model_validate(collection_job)
    )
