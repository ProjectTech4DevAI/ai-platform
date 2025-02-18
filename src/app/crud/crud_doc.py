from fastcrud import FastCRUD

from ..models.document import Document
from ..schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentUpdateInternal,
    DocumentDelete,
    DocumentSelect,
)

crud_docs = FastCRUD[
    Document,  # ModelType
    DocumentCreate,  # CreateSchemaType
    DocumentUpdate,  # UpdateSchemaType
    DocumentUpdateInternal,  # UpdateSchemaInternalType
    DocumentDelete,  # DeleteSchemaType
    DocumentSelect,  # SelectSchemaType
    None
](Document)
