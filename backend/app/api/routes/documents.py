from pathlib import Path
from urllib.parse import urlunparse

from fastapi import APIRouter, File, UploadFile
from sqlmodel import select, and_

from app.api.deps import CurrentUser, SessionDep
from app.core.cloud import AmazonCloudStorage
from app.core.util import now
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

@router.get("/rm/{doc_id}")
def delete_doc(
        session: SessionDep,
        current_user: CurrentUser,
):
    deleted_at = now()
    statement = (
        update(Document)
        .where(and_(
            Document.id == doc_id,
            Document.owner_id == current_user.id,
        ))
        .values(deleted_at=deleted_at)
    )
    session.exec(statement)

    # TODO: perform delete on the collection

@router.get("/stat/{doc_id}", response_model=Document)
def doc_info(
        session: SessionDep,
        current_user: CurrentUser,
):
    statement = (
        select(Document)
        .where(Document.id == doc_id)
    )
    docs = (session
            .exec(statement)
            .all())
    n = len(docs)
    if n == 1:
        return docs[0]

    (status_code, reason) = (500, 'not unique') if n else (400, 'not found')
    detail = f'Document "{doc_id}" {reason}'

    raise HTTPException(status_code=status_code, detail=detail)

# @router.get("/assign", response_model=DocumentList)
# def assign_doc(
#         session: SessionDep,
#         current_user: CurrentUser,
# ):
#     pass
