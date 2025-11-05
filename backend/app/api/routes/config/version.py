from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException

from app.api.deps import SessionDep, AuthContextDep
from app.crud.config import ConfigCrud, ConfigVersionCrud
from app.models import (
    ConfigVersionCreate,
    ConfigVersionPublic,
    Message,
)
from app.utils import APIResponse
from app.api.permissions import Permission, require_permission

router = APIRouter()


@router.post(
    "/{config_id}/versions",
    response_model=APIResponse[ConfigVersionPublic],
    status_code=201,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def create_version_route(
    config_id: UUID,
    version_create: ConfigVersionCreate,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    Create a new version for an existing configuration.
    The version number is automatically incremented.
    """
    version_crud = ConfigVersionCrud(
        session=session, project_id=current_user.project.id, config_id=config_id
    )
    version = version_crud.create(version_create=version_create)

    return APIResponse.success_response(
        data=ConfigVersionPublic(**version.model_dump()),
    )


@router.get(
    "/{config_id}/versions",
    response_model=APIResponse[list[ConfigVersionPublic]],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def list_versions_route(
    config_id: UUID,
    current_user: AuthContextDep,
    session: SessionDep,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum records to return"),
):
    """
    List all versions for a specific configuration.
    """
    version_crud = ConfigVersionCrud(
        session=session, project_id=current_user.project.id, config_id=config_id
    )
    versions = version_crud.read_all(
        skip=skip,
        limit=limit,
    )

    return APIResponse.success_response(
        data=versions,
    )


@router.delete(
    "/{config_id}/versions/{version_id}",
    response_model=APIResponse[Message],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def delete_version_route(
    config_id: UUID,
    version_id: UUID,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    Delete a specific version of a config.
    """
    version_crud = ConfigVersionCrud(
        session=session, project_id=current_user.project.id, config_id=config_id
    )
    version_crud.delete(version_id=version_id)

    return APIResponse.success_response(
        data=Message(message="Config Version deleted successfully"),
    )
