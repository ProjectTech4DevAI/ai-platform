import logging
from uuid import UUID
from typing import List

from fastapi import APIRouter, Query
from fastapi import Path as FastPath

from app.api.deps import SessionDep, CurrentUserOrgProject
from app.crud import (
    CollectionCrud,
    CollectionJobCrud,
    DocumentCollectionCrud,
)
from app.models import (
    DocumentPublic,
    CollectionJobStatus,
    CollectionActionType,
    CollectionJobCreate,
    CollectionJobPublic,
    CollectionJobImmediatePublic,
    CollectionWithDocsPublic,
)
from app.models.collection import (
    CreationRequest,
    CallbackRequest,
    DeletionRequest,
    CollectionPublic,
)
from app.utils import APIResponse, load_description
from app.services.collections import (
    create_collection as create_service,
    delete_collection as delete_service,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])
collection_callback_router = APIRouter()


@collection_callback_router.post(
    "{$callback_url}",
    name="collection_callback",
)
def collection_callback_notification(body: APIResponse[CollectionJobPublic]):
    """
    Callback endpoint specification for collection creation/deletion.

    The callback will receive:
    - On success: APIResponse with success=True and data containing CollectionJobPublic
    - On failure: APIResponse with success=False and error message
    - metadata field will always be included if provided in the request
    """
    ...


@router.get(
    "/",
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
    "/",
    description=load_description("collections/create.md"),
    response_model=APIResponse[CollectionJobImmediatePublic],
    callbacks=collection_callback_router.routes,
    response_model_exclude_none=True,
)
def create_collection(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: CreationRequest,
):
    collection_job_crud = CollectionJobCrud(session, current_user.project_id)
    collection_job = collection_job_crud.create(
        CollectionJobCreate(
            action_type=CollectionActionType.CREATE,
            project_id=current_user.project_id,
            status=CollectionJobStatus.PENDING,
        )
    )

    # True iff both model and instructions were provided in the request body
    with_assistant = bool(
        getattr(request, "model", None) and getattr(request, "instructions", None)
    )

    create_service.start_job(
        db=session,
        request=request,
        collection_job_id=collection_job.id,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
        with_assistant=with_assistant,
    )

    metadata = None
    if not with_assistant:
        metadata = {
            "note": (
                "This job will create a vector store only (no Assistant). "
                "Assistant creation happens when both 'model' and 'instructions' are included."
            )
        }

    return APIResponse.success_response(
        CollectionJobImmediatePublic.model_validate(collection_job), metadata=metadata
    )


@router.delete(
    "/{collection_id}",
    description=load_description("collections/delete.md"),
    response_model=APIResponse[CollectionJobImmediatePublic],
    callbacks=collection_callback_router.routes,
    response_model_exclude_none=True,
)
def delete_collection(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    collection_id: UUID = FastPath(description="Collection to delete"),
    request: CallbackRequest | None = None,
):
    _ = CollectionCrud(session, current_user.project_id).read_one(collection_id)

    deletion_request = DeletionRequest(
        collection_id=collection_id,
        callback_url=request.callback_url if request else None,
    )

    collection_job_crud = CollectionJobCrud(session, current_user.project_id)
    collection_job = collection_job_crud.create(
        CollectionJobCreate(
            action_type=CollectionActionType.DELETE,
            project_id=current_user.project_id,
            status=CollectionJobStatus.PENDING,
            collection_id=collection_id,
        )
    )

    delete_service.start_job(
        db=session,
        request=deletion_request,
        collection_job_id=collection_job.id,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )

    return APIResponse.success_response(
        CollectionJobImmediatePublic.model_validate(collection_job)
    )


@router.get(
    "/{collection_id}",
    description=load_description("collections/info.md"),
    response_model=APIResponse[CollectionWithDocsPublic],
)
def collection_info(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    collection_id: UUID = FastPath(description="Collection to retrieve"),
    include_docs: bool = Query(
        True,
        description="If true, include documents linked to this collection",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    collection_crud = CollectionCrud(session, current_user.project_id)
    collection = collection_crud.read_one(collection_id)

    collection_with_docs = CollectionWithDocsPublic.model_validate(collection)

    if include_docs:
        document_collection_crud = DocumentCollectionCrud(session)
        docs = document_collection_crud.read(collection, skip, limit)
        collection_with_docs.documents = [
            DocumentPublic.model_validate(doc) for doc in docs
        ]

    return APIResponse.success_response(collection_with_docs)
