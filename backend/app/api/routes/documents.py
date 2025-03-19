from uuid import UUID, uuid4
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException
from sqlmodel import select, update, and_

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
        session: SessionDep,
        current_user: CurrentUser,
        src: UploadFile = File(...),
):
    storage = AmazonCloudStorage(current_user)
    basename = uuid4()
    try:
        object_store_url = storage.put(src, str(basename))
    except ConnectionError as err:
        raise HTTPException(status_code=500, detail=str(err))

    document = Document(
        id=basename,
        owner_id=current_user.id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    return document.id

@router.get("/rm/{doc_id}")
def delete_doc(
        session: SessionDep,
        current_user: CurrentUser,
        doc_id: UUID,
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
        doc_id: UUID,
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
