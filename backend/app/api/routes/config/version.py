from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, Path

from app.api.deps import SessionDep, AuthContextDep
from app.crud.config import ConfigCrud, ConfigVersionCrud
from app.models import (
    ConfigVersionCreate,
    ConfigVersionPublic,
    Message,
    ConfigVersionItems,
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
    response_model=APIResponse[list[ConfigVersionItems]],
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


@router.get(
    "/{config_id}/versions/{version_number}",
    response_model=APIResponse[ConfigVersionPublic],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def get_version_route(
    config_id: UUID,
    current_user: AuthContextDep,
    session: SessionDep,
    version_number: int = Path(
        ..., ge=1, description="The version number of the config"
    ),
):
    """
    Get a specific version of a config.
    """
    version_crud = ConfigVersionCrud(
        session=session, project_id=current_user.project.id, config_id=config_id
    )
    version = version_crud.read_one(version_number=version_number)
    if version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Config Version with number '{version_number}' not found for config '{config_id}'",
        )

    return APIResponse.success_response(
        data=version,
    )


@router.delete(
    "/{config_id}/versions/{version_number}",
    response_model=APIResponse[Message],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def delete_version_route(
    config_id: UUID,
    current_user: AuthContextDep,
    session: SessionDep,
    version_number: int = Path(
        ..., ge=1, description="The version number of the config"
    ),
):
    """
    Delete a specific version of a config.
    """
    version_crud = ConfigVersionCrud(
        session=session, project_id=current_user.project.id, config_id=config_id
    )
    version_crud.delete(version_number=version_number)

    return APIResponse.success_response(
        data=Message(message="Config Version deleted successfully"),
    )
