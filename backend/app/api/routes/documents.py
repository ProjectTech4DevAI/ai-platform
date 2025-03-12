from fastapi import APIRouter
from sqlmodel import select, and_

from app.api.deps import CurrentUser, SessionDep
from app.models import Document, DocumentList

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "/ls",
    response_model=DocumentList,
)
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
