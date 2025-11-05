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

