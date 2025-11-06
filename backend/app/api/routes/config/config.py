from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException

from app.api.deps import SessionDep, AuthContextDep
from app.crud.config import ConfigCrud
from app.models import (
    Config,
    ConfigCreate,
    ConfigUpdate,
    ConfigPublic,
    ConfigWithVersion,
    ConfigVersion,
    Message,
)
from app.utils import APIResponse
from app.api.permissions import Permission, require_permission

router = APIRouter()


@router.post(
    "/",
    response_model=APIResponse[ConfigWithVersion],
    status_code=201,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def create_config_route(
    config_create: ConfigCreate,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    create new config along with initial version
    """
    config_crud = ConfigCrud(session=session, project_id=current_user.project.id)
    config, version = config_crud.create(config_create)

    response = ConfigWithVersion(**config.model_dump(), version=version)

    return APIResponse.success_response(
        data=response,
    )


@router.get(
    "/",
    response_model=APIResponse[list[ConfigPublic]],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def list_configs_route(
    current_user: AuthContextDep,
    session: SessionDep,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum records to return"),
):
    """
    List all configurations for the current project.
    """

    # Decide how to handle pagination effectively
    config_crud = ConfigCrud(session=session, project_id=current_user.project.id)
    configs = config_crud.read_all(skip=skip, limit=limit)
    return APIResponse.success_response(
        data=configs,
    )


@router.get(
    "/{config_id}",
    response_model=APIResponse[ConfigPublic],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def get_config_route(
    config_id: UUID,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    Get a specific configuration by its ID.
    """
    config_crud = ConfigCrud(session=session, project_id=current_user.project.id)
    config = config_crud.exists(config_id=config_id)
    return APIResponse.success_response(
        data=config,
    )


@router.patch(
    "/{config_id}",
    response_model=APIResponse[ConfigPublic],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def update_config_route(
    config_id: UUID,
    config_update: ConfigUpdate,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    Update a specific configuration.
    """
    config_crud = ConfigCrud(session=session, project_id=current_user.project.id)
    config = config_crud.update(config_id=config_id, config_update=config_update)

    return APIResponse.success_response(
        data=config,
    )


@router.delete(
    "/{config_id}",
    response_model=APIResponse[Message],
    status_code=200,
    dependencies=[Depends(require_permission(Permission.REQUIRE_PROJECT))],
)
def delete_config_route(
    config_id: UUID,
    current_user: AuthContextDep,
    session: SessionDep,
):
    """
    Delete a specific configuration.
    """
    config_crud = ConfigCrud(session=session, project_id=current_user.project.id)
    config_crud.delete(config_id=config_id)

    return APIResponse.success_response(
        data=Message(message="Config deleted successfully"),
    )
