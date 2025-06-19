from uuid import UUID
from typing import Optional, List

from sqlmodel import Session, select, and_

from app.models import Document
from app.core.util import now
from app.core.exception_handlers import HTTPException


class DocumentCrud:
    def __init__(self, session: Session, owner_id: int):
        self.session = session
        self.owner_id = owner_id

    def read_one(self, doc_id: UUID):
        statement = select(Document).where(
            and_(
                Document.owner_id == self.owner_id,
                Document.id == doc_id,
            )
        )

        result = self.session.exec(statement).one_or_none()
        if result is None:
            raise HTTPException(status_code=404, detail="Document not found")

        return result

    def read_many(
        self,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        statement = select(Document).where(
            and_(
                Document.owner_id == self.owner_id,
                Document.deleted_at.is_(None),
            )
        )
        if skip is not None:
            if skip < 0:
                raise ValueError(f"Negative skip: {skip}")
            statement = statement.offset(skip)
        if limit is not None:
            if limit < 0:
                raise ValueError(f"Negative limit: {limit}")
            statement = statement.limit(limit)

        return self.session.exec(statement).all()

    def read_each(self, doc_ids: List[UUID]):
        statement = select(Document).where(
            and_(
                Document.owner_id == self.owner_id,
                Document.id.in_(doc_ids),
            )
        )
        results = self.session.exec(statement).all()

        (m, n) = map(len, (results, doc_ids))
        if m != n:
            raise ValueError(f"Requested {n} retrieved {m}")

        return results

    def update(self, document: Document):
        if not document.owner_id:
            document.owner_id = self.owner_id
        elif document.owner_id != self.owner_id:
            error = "Invalid document ownership: owner={} attempter={}".format(
                self.owner_id,
                document.owner_id,
            )
            raise PermissionError(error)

        document.updated_at = now()

        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)

        return document

    def delete(self, doc_id: UUID):
        document = self.read_one(doc_id)
        document.deleted_at = now()
        document.updated_at = now()

        return self.update(document)
