from uuid import UUID
from typing import Optional

from sqlmodel import Session, select, update, and_

from app.models import Document, DocumentList
from app.core.util import now

class DocumentCrud:
    def __init__(self, session: Session, owner_id: UUID):
        self.session = session
        self.owner_id = owner_id

    def read_one(self, doc_id: UUID):
        statement = (
            select(Document)
            .where(and_(
                Document.owner_id == self.owner_id,
                Document.id == doc_id,
            ))
        )

        return self.session.exec(statement).one()

    def read_many(
            self,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ):
        statement = (
            select(Document)
            .where(and_(
                Document.owner_id == self.owner_id,
                Document.deleted_at.is_(None),
            ))
        )
        if skip is not None:
            if skip < 0:
                raise ValueError(f'Negative skip: {skip}')
            statement = statement.offset(skip)
        if limit is not None:
            if limit < 0:
                raise ValueError(f'Negative limit: {limit}')
            statement = statement.limit(limit)
        docs = self.session.exec(statement).all()

        return DocumentList(docs=docs)

    def update(self, document: Document):
        if not document.owner_id:
            document.owner_id = self.owner_id
        elif document.owner_id != self.owner_id:
            error = 'Invalid document ownership: owner={} attempter={}'.format(
                self.owner_id,
                document.owner_id,
            )
            raise PermissionError(error)

        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)

        return document

    def delete(self, doc_id: UUID):
        document = self.read_one(doc_id)
        document.deleted_at = now()

        return self.update(document)
