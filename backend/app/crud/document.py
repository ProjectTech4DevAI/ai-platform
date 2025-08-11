import logging
from uuid import UUID
from typing import Optional, List

from sqlmodel import Session, select, and_

from app.models import Document
from app.core.util import now
from app.core.exception_handlers import HTTPException

logger = logging.getLogger(__name__)


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
            logger.warning(
                f"[DocumentCrud.read_one] Document not found | {{'doc_id': '{doc_id}', 'owner_id': {self.owner_id}}}"
            )
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
                try:
                    raise ValueError(f"Negative skip: {skip}")
                except ValueError as err:
                    logger.error(
                        f"[DocumentCrud.read_many] Invalid skip value | {{'owner_id': {self.owner_id}, 'skip': {skip}, 'error': '{str(err)}'}}",
                        exc_info=True,
                    )
                    raise
            statement = statement.offset(skip)

        if limit is not None:
            if limit < 0:
                try:
                    raise ValueError(f"Negative limit: {limit}")
                except ValueError as err:
                    logger.error(
                        f"[DocumentCrud.read_many] Invalid limit value | {{'owner_id': {self.owner_id}, 'limit': {limit}, 'error': '{str(err)}'}}",
                        exc_info=True,
                    )
                    raise
            statement = statement.limit(limit)

        documents = self.session.exec(statement).all()
        return documents

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
            try:
                raise ValueError(f"Requested atleast {n} document retrieved {m}")
            except ValueError as err:
                logger.error(
                    f"[DocumentCrud.read_each] Mismatch in retrieved documents | {{'owner_id': {self.owner_id}, 'requested_count': {n}, 'retrieved_count': {m}}}",
                    exc_info=True,
                )
                raise

        return results

    def update(self, document: Document):
        if not document.owner_id:
            document.owner_id = self.owner_id
        elif document.owner_id != self.owner_id:
            error = "Invalid document ownership: owner={} attempter={}".format(
                self.owner_id,
                document.owner_id,
            )
            try:
                raise PermissionError(error)
            except PermissionError as err:
                logger.error(
                    f"[DocumentCrud.update] Permission error | {{'doc_id': '{document.id}', 'error': '{str(err)}'}}",
                    exc_info=True,
                )
                raise
        document.updated_at = now()

        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        logger.info(
            f"[DocumentCrud.update] Document updated successfully | {{'doc_id': '{document.id}', 'owner_id': {self.owner_id}}}"
        )

        return document

    def delete(self, doc_id: UUID):
        document = self.read_one(doc_id)
        document.deleted_at = now()
        document.updated_at = now()

        updated_document = self.update(document)
        logger.info(
            f"[DocumentCrud.delete] Document deleted successfully | {{'doc_id': '{doc_id}', 'owner_id': {self.owner_id}}}"
        )
        return updated_document
