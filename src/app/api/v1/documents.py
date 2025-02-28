from typing import Annotated, Depends

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import (
    PaginatedListResponse,
    compute_offset,
    paginated_response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...crud.crud_docs import crud_docs
from ...schemas.document import DocumentSelect
from ...schemas.user import UserRead

router = APIRouter(tags=["documents"])


@router.get("/list", response_model=PaginatedListResponse[DocumentSelect])
async def list_documents(
        request: Request, ### ???
        db: Annotated[AsyncSession, Depends(async_get_db)],
        current_user: Annotated[UserRead, Depends(get_current_user)], ### ???
        page: int = 1,
        items_per_page: int = 10,
):
    crud_data = crud_docs.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        schema_to_select=DocumentSelect,
        # SQL kwargs filters
        owner=current_user,
        is_deleted=False,
    )

    return paginated_response(
        crud_data=crud_data,
        page=page,
        items_per_page=items_per_page,
    )
