import inspect
import logging
from uuid import UUID
from typing import List, Union
from dataclasses import asdict

from fastapi import APIRouter, Query
from fastapi import Path as FastPath


from app.api.deps import SessionDep, CurrentUserOrgProject
from app.crud import (
    CollectionCrud,
    CollectionJobCrud,
    DocumentCollectionCrud,
)
from app.models import DocumentPublic, CollectionJobStatus, CollectionJobPublic
from app.models.collection import (
    ResponsePayload,
    CreationRequest,
    DeletionRequest,
    CollectionPublic,
)
from app.utils import APIResponse, load_description
from app.services.collections.helpers import extract_error_message
from app.services.collections import (
    create_collection as create_service,
    delete_collection as delete_service,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


@router.post(
    "/create",
    description=load_description("collections/create.md"),
)
def create_collection(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: CreationRequest,
):
    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload(status="processing", route=route)

    create_service.start_job(
        db=session,
        request=request.model_dump(),
        payload=payload.model_dump(),
        collection_job_id=UUID(payload.key),
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )

    logger.info(
        f"[create_collection] Background task for collection creation scheduled | "
        f"{{'collection_job_id': '{payload.key}'}}"
    )
    return APIResponse.success_response(
        data=None, metadata=payload.model_dump(mode="json")
    )


@router.post(
    "/delete",
    description=load_description("collections/delete.md"),
)
def delete_collection(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: DeletionRequest,
):
    collection_crud = CollectionCrud(session, current_user.project_id)
    collection = collection_crud.read_one(request.collection_id)

    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload(status="processing", route=route)

    delete_service.start_job(
        db=session,
        request=request.model_dump(),
        payload=payload.model_dump(),
        collection=collection,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )

    logger.info(
        f"[delete_collection] Background task for deletion scheduled | "
        f"{{'collection_id': '{request.collection_id}'}}"
    )
    return APIResponse.success_response(
        data=None, metadata=payload.model_dump(mode="json")
    )


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


@router.get(
    "/info/{collection_id}",
    description=load_description("collections/info.md"),
    response_model=APIResponse[CollectionPublic],
)
def collection_info(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    collection_id: UUID = FastPath(description="Collection to retrieve"),
):
    collection_crud = CollectionCrud(session, current_user.project_id)
    collection = collection_crud.read_one(collection_id)

    return APIResponse.success_response(collection)


@router.get(
    "/list",
    description=load_description("collections/list.md"),
    response_model=APIResponse[List[CollectionPublic]],
)
def list_collections(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
):
    collection_crud = CollectionCrud(session, current_user.project_id)
    rows = collection_crud.read_all()

    return APIResponse.success_response(rows)


@router.post(
    "/docs/{collection_id}",
    description=load_description("collections/docs.md"),
    response_model=APIResponse[List[DocumentPublic]],
)
def collection_documents(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    collection_id: UUID = FastPath(description="Collection to retrieve"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    collection_crud = CollectionCrud(session, current_user.project_id)
    document_collection_crud = DocumentCollectionCrud(session)
    collection = collection_crud.read_one(collection_id)
    data = document_collection_crud.read(collection, skip, limit)
    return APIResponse.success_response(data)
