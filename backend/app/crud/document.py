from uuid import UUID
from typing import Optional

from sqlmodel import Session, select, update, and_

from app.models import Document, DocumentList
from app.core.util import now

class CrudObject:
    def __init__(self, session: Session):
        self.session = session

class DocumentCrud(CrudObject):
    def read_one(self, doc_id: UUID):
        statement = (
            select(Document)
            .where(Document.id == doc_id)
        )

        return self.session.exec(statement).one()

    def read_many(
            self,
            owner_id: UUID,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ):
        statement = (
            select(Document)
            .where(and_(
                Document.owner_id == owner_id,
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
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)

        return document

    def delete(self, doc_id: UUID, owner_id: UUID):
        statement = (
            update(Document)
            .where(and_(
                Document.id == doc_id,
                Document.owner_id == owner_id,
            ))
            .values(deleted_at=now())
        )
        result = self.session.exec(statement)
        if not result.rowcount:
            raise FileNotFoundError(f'Item "{doc_id}" not found')

        self.session.commit()
