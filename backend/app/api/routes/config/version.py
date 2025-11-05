from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException

from app.api.deps import SessionDep, AuthContextDep
from app.models import (
    ConfigVersionCreate,
    ConfigVersionPublic,
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
    pass