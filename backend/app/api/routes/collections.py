import inspect
import logging
from uuid import UUID
from typing import List
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Query
from fastapi import Path as FastPath


from app.api.deps import SessionDep, CurrentUserOrgProject
from app.crud import (
    CollectionCrud,
    DocumentCollectionCrud,
)
from app.models import Collection, DocumentPublic
from app.models.collection import (
    CollectionStatus,
    ResponsePayload,
    CreationRequest,
    DeletionRequest,
)
from app.utils import APIResponse, load_description, get_openai_client
from app.services.collections.helpers import extract_error_message
from app.services.collections import (
    create_collection as create_services,
    delete_collection as delete_services,
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
    background_tasks: BackgroundTasks,
):
    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload("processing", route)

    collection = Collection(
        id=UUID(payload.key),
        organization_id=current_user.organization_id,
        project_id=current_user.project_id,
        status=CollectionStatus.processing,
    )

    collection_crud = CollectionCrud(session, current_user.project_id)
    collection_crud.create(collection)

    create_services.start_job(
        db=session,
        request=request.model_dump(),
        payload=asdict(payload),
        collection=collection,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )

    logger.info(
        f"[create_collection] Background task for collection creation scheduled | "
        f"{{'collection_id': '{collection.id}'}}"
    )
    return APIResponse.success_response(data=None, metadata=asdict(payload))


@router.post(
    "/delete",
    description=load_description("collections/delete.md"),
)
def delete_collection(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: DeletionRequest,
    background_tasks: BackgroundTasks,
):
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )

    collection_crud = CollectionCrud(session, current_user.project_id)
    collection = collection_crud.read_one(request.collection_id)

    this = inspect.currentframe()
    route = router.url_path_for(this.f_code.co_name)
    payload = ResponsePayload("processing", route)

    delete_services.start_job(
        db=session,
        request=request.model_dump(),
        payload=asdict(payload),
        collection=collection,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )

    logger.info(
        f"[delete_collection] Background task for deletion scheduled | "
        f"{{'collection_id': '{request.collection_id}'}}"
    )
    return APIResponse.success_response(data=None, metadata=asdict(payload))


@router.post(
    "/info/{collection_id}",
    description=load_description("collections/info.md"),
    response_model=APIResponse[Collection],
)
def collection_info(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    collection_id: UUID = FastPath(description="Collection to retrieve"),
):
    collection_crud = CollectionCrud(session, current_user.project_id)
    data = collection_crud.read_one(collection_id)

    err = getattr(data, "error_message", None)
    if err:
        data.error_message = extract_error_message(err)

    return APIResponse.success_response(data)


@router.post(
    "/list",
    description=load_description("collections/list.md"),
    response_model=APIResponse[List[Collection]],
)
def list_collections(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
):
    collection_crud = CollectionCrud(session, current_user.project_id)
    rows = collection_crud.read_all()

    for c in rows:
        if getattr(c, "error_message", None):
            c.error_message = extract_error_message(c.error_message)

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
