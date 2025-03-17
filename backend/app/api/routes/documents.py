from pathlib import Path
from urllib.parse import urlunparse

from fastapi import APIRouter, File, UploadFile
from sqlmodel import select, and_

from app.api.deps import CurrentUser, SessionDep
from app.core.cloud import AmazonCloudStorage
from app.models import Document, DocumentList

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/ls", response_model=DocumentList)
def list_docs(
        session: SessionDep,
        current_user: CurrentUser,
        skip: int = 0,
        limit: int = 100,
):
    statement = (
        select(Document)
        .where(and_(
            Document.owner_id == current_user.id,
            Document.deleted_at.is_(None),
        ))
        .offset(skip)
        .limit(limit)
    )
    docs = (session
            .exec(statement)
            .all())

    return DocumentList(docs=docs)

@router.post("/cp")
def upload_doc(
        doc: UploadFile,
        session: SessionDep,
        current_user: CurrentUser,
):
    storage = AmazonCloudStorage(current_user)
    try:
        object_store_url = storage.put(doc)
    except ConnectionError as err:
        raise HTTPException(status_code=500, detail=str(err))
    fname_internal = Path(object_store_url.path)

    document = Document(
        owner_id=user.id,
        fname_external=Path(doc.filename),
        fname_internal=fname_internal.stem,
        object_store_url=urlunparse(object_store_url),
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    return document.id
