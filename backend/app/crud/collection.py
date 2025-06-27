import logging
import functools as ft
from uuid import UUID
from typing import Optional
import logging
from sqlmodel import Session, func, select, and_

from app.models import Document, Collection, DocumentCollection
from app.core.util import now
from app.models.collection import CollectionStatus

from .document_collection import DocumentCollectionCrud

logger = logging.getLogger(__name__)


class CollectionCrud:
    def __init__(self, session: Session, owner_id: int):
        self.session = session
        self.owner_id = owner_id

    def _update(self, collection: Collection):
        if not collection.owner_id:
            collection.owner_id = self.owner_id
        elif collection.owner_id != self.owner_id:
            err = "Invalid collection ownership: owner={} attempter={}".format(
                self.owner_id,
                collection.owner_id,
            )
            logger.error(
                f"[CollectionCrud._update] Permission error | {{'collection_id': '{collection.id}', 'error': '{err}'}}",
                exc_info=True,
            )
            raise PermissionError(err)

        self.session.add(collection)
        self.session.commit()
        self.session.refresh(collection)
        logger.info(
            f"[CollectionCrud._update] Collection updated successfully | {{'collection_id': '{collection.id}'}}"
        )

        return collection

    def _exists(self, collection: Collection):
        present = (
            self.session.query(func.count(Collection.id))
            .filter(
                Collection.llm_service_id == collection.llm_service_id,
                Collection.llm_service_name == collection.llm_service_name,
            )
            .scalar()
        )
        logger.info(
            f"[CollectionCrud._exists] Existence check completed | {{'llm_service_id': '{collection.llm_service_id}', 'exists': {bool(present)}}}"
        )

        return bool(present)

    def create(
        self,
        collection: Collection,
        documents: Optional[list[Document]] = None,
    ):
        try:
            existing = self.read_one(collection.id)
            if existing.status == CollectionStatus.failed:
                self._update(collection)
            else:
                raise FileExistsError("Collection already present")
        except:
            self.session.add(collection)
            self.session.commit()

        if documents:
            dc_crud = DocumentCollectionCrud(self.session)
            dc_crud.create(collection, documents)

        return collection

    def read_one(self, collection_id: UUID):
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.id == collection_id,
            )
        )

        collection = self.session.exec(statement).one()
        return collection

    def read_all(self):
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.deleted_at.is_(None),
            )
        )

        collections = self.session.exec(statement).all()
        return collections

    @ft.singledispatchmethod
    def delete(self, model, remote):  # remote should be an OpenAICrud
        logger.error(
            f"[CollectionCrud.delete] Invalid model type | {{'model_type': '{type(model).__name__}'}}",
            exc_info=True,
        )
        raise TypeError(type(model))

    @delete.register
    def _(self, model: Collection, remote):
        remote.delete(model.llm_service_id)
        model.deleted_at = now()
        collection = self._update(model)
        logger.info(
            f"[CollectionCrud.delete] Collection deleted successfully | {{'collection_id': '{model.id}'}}"
        )
        return collection

    @delete.register
    def _(self, model: Document, remote):
        statement = (
            select(Collection)
            .join(
                DocumentCollection,
                DocumentCollection.collection_id == Collection.id,
            )
            .where(DocumentCollection.document_id == model.id)
            .distinct()
        )

        for c in self.session.execute(statement):
            self.delete(c.Collection, remote)
        self.session.refresh(model)
        logger.info(
            f"[CollectionCrud.delete] Document deletion from collections completed | {{'document_id': '{model.id}'}}"
        )

        return model
