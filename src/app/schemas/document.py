from uuid import UUID
from typing import Annotated
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel, AnyUrl

#
# ModelType
#
class Document(BaseModel):
    id: int
    owner: int
    fname_internal: UUID
    fname_external: Path
    object_store_url: AnyUrl
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
    is_deleted: bool

#
# CreateSchemaType
#
class DocumentCreate(BaseModel):
    owner: int
    fname_external: Path
    object_store_url: AnyUrl

#
# UpdateSchemaType
#
class DocumentUpdate(BaseModel):
    fname_external: Path

#
# UpdateSchemaInternalType
#
class DocumentUpdateInternal(DocumentUpdate):
    updated_at: datetime

#
# DeleteSchemaType
#
class DocumentDelete(BaseModel):
    fname_internal: UUID

#
# SelectSchemaType
#
class DocumentSelect(BaseModel):
    pass
