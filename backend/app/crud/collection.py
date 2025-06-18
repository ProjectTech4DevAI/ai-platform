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
        logger.info(
            f"[CollectionCrud.init] Initialized CollectionCrud | {{'owner_id': {owner_id}}}"
        )

    def _update(self, collection: Collection):
        logger.info(
            f"[CollectionCrud._update] Starting collection update | {{'collection_id': '{collection.id}', 'owner_id': {self.owner_id}}}"
        )
        if not collection.owner_id:
            logger.info(
                f"[CollectionCrud._update] Assigning owner ID | {{'collection_id': '{collection.id}', 'owner_id': {self.owner_id}}}"
            )
            collection.owner_id = self.owner_id
        elif collection.owner_id != self.owner_id:
            logger.warning(
                f"[CollectionCrud._update] Ownership mismatch detected | {{'collection_id': '{collection.id}', 'owner_id': {collection.owner_id}, 'attempted_owner_id': {self.owner_id}}}"
            )
            err = "Invalid collection ownership: owner={} attempter={}".format(
                self.owner_id,
                collection.owner_id,
            )
            logger.error(
                f"[CollectionCrud._update] Permission error | {{'collection_id': '{collection.id}', 'error': '{err}'}}"
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
        logger.info(
            f"[CollectionCrud._exists] Checking if collection exists | {{'llm_service_id': '{collection.llm_service_id}', 'llm_service_name': '{collection.llm_service_name}'}}"
        )
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
        logger.info(
            f"[CollectionCrud.read_one] Retrieving collection | {{'collection_id': '{collection_id}', 'owner_id': {self.owner_id}}}"
        )
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.id == collection_id,
            )
        )

        collection = self.session.exec(statement).one()
        logger.info(
            f"[CollectionCrud.read_one] Collection retrieved successfully | {{'collection_id': '{collection_id}'}}"
        )
        return collection

    def read_all(self):
        logger.info(
            f"[CollectionCrud.read_all] Retrieving all collections | {{'owner_id': {self.owner_id}}}"
        )
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.deleted_at.is_(None),
            )
        )

        collections = self.session.exec(statement).all()
        logger.info(
            f"[CollectionCrud.read_all] Collections retrieved successfully | {{'owner_id': {self.owner_id}, 'collection_count': {len(collections)}}}"
        )
        return collections

    @ft.singledispatchmethod
    def delete(self, model, remote):  # remote should be an OpenAICrud
        logger.error(
            f"[CollectionCrud.delete] Invalid model type | {{'model_type': '{type(model).__name__}'}}"
        )
        raise TypeError(type(model))

    @delete.register
    def _(self, model: Collection, remote):
        logger.info(
            f"[CollectionCrud.delete] Starting collection deletion | {{'collection_id': '{model.id}', 'llm_service_id': '{model.llm_service_id}'}}"
        )
        remote.delete(model.llm_service_id)
        model.deleted_at = now()
        collection = self._update(model)
        logger.info(
            f"[CollectionCrud.delete] Collection deleted successfully | {{'collection_id': '{model.id}'}}"
        )
        return collection

    @delete.register
    def _(self, model: Document, remote):
        logger.info(
            f"[CollectionCrud.delete] Starting document deletion from collections | {{'document_id': '{model.id}'}}"
        )
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
            logger.info(
                f"[CollectionCrud.delete] Deleting collection associated with document | {{'document_id': '{model.id}', 'collection_id': '{c.Collection.id}'}}"
            )
            self.delete(c.Collection, remote)
        self.session.refresh(model)
        logger.info(
            f"[CollectionCrud.delete] Document deletion from collections completed | {{'document_id': '{model.id}'}}"
        )

        return model