from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import (
    PaginatedListResponse,
    compute_offset,
    paginated_response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...schemas.user import UserRead
from ...schemas.document import DocumentRead

router = APIRouter(tags=['documents'])

@router.get(
    '/docs/{username}',
    response_model=PaginatedListResponse[DocumentRead],
)
async def ls_documents(
        request: Request,
        username: str,
        db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict:
    db_user: UserRead | None = await crud_users.get(
        db=db,
        schema_to_select=UserRead,
        username=username,
        is_deleted=False,
    )
    if db_user is None:
        raise NotFoundException(f'User "{username}" not found')

    return db_user
