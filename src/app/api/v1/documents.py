from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import (
    PaginatedListResponse,
    compute_offset,
    paginated_response,
)
from sqlalchemy.ext.asyncio import AsyncSession

# from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...crud.crud_docs import crud_docs
from ...schemas.document import DocumentSelect
from ...schemas.user import UserRead

router = APIRouter(tags=["documents"])

### <START> authentication coming from future @nishika26 PR
from fastapi import Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

api_key_header = APIKeyHeader(name="Authorization", auto_error=True)


class CredentialsRead(BaseModel):
    organization_id: int
    organization_name: str
    project_id: int
    project_name: str
    api_key: str


def get_current_org(
    token: str = Security(api_key_header),
    db: AsyncSession = Depends(async_get_db),
):
    return CredentialsRead(0, "ACME", 0, "My project", token)


### <END>


@router.get(
    "/documents/list",
    response_model=PaginatedListResponse[DocumentSelect],
)
async def list_documents(
    request: Request,  ### ???
    db: Annotated[AsyncSession, Depends(async_get_db)],
    creds: Annotated[CredentialsRead, Depends(get_current_org)],
    page: int = 1,
    items_per_page: int = 10,
):
    crud_data = crud_docs.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        schema_to_select=DocumentSelect,
        # SQL kwargs filters
        owner=creds.project_id,
        is_deleted=False,
    )

    return paginated_response(
        crud_data=crud_data,
        page=page,
        items_per_page=items_per_page,
    )
