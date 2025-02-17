from fastcrud import FastCRUD

from ..models.tag import Tag
from ..schemas.tag import TagCreateInternal, TagDelete, TagUpdate, TagUpdateInternal

CRUDTag = FastCRUD[Tag, TagCreateInternal, TagUpdate, TagUpdateInternal, TagDelete]
crud_tags = CRUDTag(Tag)
