from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, AuthContextDep
from app.crud.api_key import APIKeyCrud
from app.models import APIKeyPublic, APIKeyCreateResponse, Message
from app.utils import APIResponse
from app.api.permissions import Permission, require_permission

router = APIRouter(prefix="/apikeys", tags=["API Keys"])


@router.post(
    "/",
    response_model=APIResponse[APIKeyCreateResponse],
    status_code=201,
    dependencies=[Depends(require_permission(Permission.SUPERUSER))],
)
def create_api_key_route(
    project_id: int,
    user_id: int,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    Create a new API key for the project and user, Restricted to Superuser.

    The raw API key is returned only once during creation.
    Store it securely as it cannot be retrieved again.
    """
    api_key_crud = APIKeyCrud(session=session, project_id=project_id)
    raw_key, api_key = api_key_crud.create(
        user_id=user_id,
        project_id=project_id,
    )

    api_key = APIKeyCreateResponse(**api_key.model_dump(), key=raw_key)
    return APIResponse.success_response(
        data=api_key,
        metadata={
            "message": "The raw API key is returned only once during creation. Store it securely as it cannot be retrieved again."
        },
    )


@router.get(
    "/",
    response_model=APIResponse[list[APIKeyPublic]],
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def list_api_keys_route(
    current_user: AuthContextDep,
    session: SessionDep,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum records to return"),
):
    """
    List all API keys for the current project.

    Returns key prefix for security - the full key is only shown during creation.
    Supports pagination via skip and limit parameters.
    """
    crud = APIKeyCrud(session, current_user.project_id)
    api_keys = crud.read_all(skip=skip, limit=limit)

    return APIResponse.success_response(api_keys)


@router.delete(
    "/{key_id}",
    response_model=APIResponse[Message],
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def delete_api_key_route(
    key_id: UUID,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    Delete an API key by its ID.
    """
    api_key_crud = APIKeyCrud(session=session, project_id=current_user.project_id)
    api_key_crud.delete(key_id=key_id)

    return APIResponse.success_response(Message(message="API Key deleted successfully"))
