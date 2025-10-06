import logging
import functools as ft
from uuid import UUID
from typing import Optional
import logging

from fastapi import HTTPException
from sqlmodel import Session, func, select, and_

from app.models import Document, Collection, DocumentCollection
from app.core.util import now

from ..document_collection import DocumentCollectionCrud

logger = logging.getLogger(__name__)


class CollectionCrud:
    def __init__(self, session: Session, project_id: int):
        self.session = session
        self.project_id = project_id

    def _update(self, collection: Collection):
        if not collection.project_id:
            collection.project_id = self.project_id
        elif collection.project_id != self.project_id:
            err = "Invalid collection ownership: owner_project={} attempter={}".format(
                self.project_id,
                collection.project_id,
            )
            try:
                raise PermissionError(err)
            except PermissionError as e:
                logger.error(
                    f"[CollectionCrud._update] Permission error | {{'collection_id': '{collection.id}', 'error': '{str(e)}'}}",
                    exc_info=True,
                )
                raise

        self.session.add(collection)
        self.session.commit()
        self.session.refresh(collection)
        logger.info(
            f"[CollectionCrud._update] Collection updated successfully | {{'collection_id': '{collection.id}'}}"
        )

        return collection

    def _exists(self, collection: Collection) -> bool:
        stmt = (
            select(Collection.id)
            .where(
                (Collection.llm_service_id == collection.llm_service_id)
                & (Collection.llm_service_name == collection.llm_service_name)
            )
            .limit(1)
        )
        present = self.session.exec(stmt).first() is not None

        logger.info(
            "[CollectionCrud._exists] Existence check completed | "
            f"{{'llm_service_id': '{collection.llm_service_id}', 'exists': {present}}}"
        )
        return present

    def create(
        self,
        collection: Collection,
        documents: Optional[list[Document]] = None,
    ):
        try:
            existing = self.read_one(collection.id)

            raise FileExistsError("Collection already present")
        except:
            self.session.add(collection)
            self.session.commit()

        if documents:
            dc_crud = DocumentCollectionCrud(self.session)
            dc_crud.create(collection, documents)

        return collection

    def read_one(self, collection_id: UUID) -> Collection:
        statement = select(Collection).where(
            and_(
                Collection.project_id == self.project_id,
                Collection.id == collection_id,
                Collection.deleted_at.is_(None),
            )
        )

        collection = self.session.exec(statement).first()
        if collection is None:
            logger.error(
                "[CollectionCrud.read_one] Collection not found | "
                f"{{'project_id': '{self.project_id}', 'collection_id': '{collection_id}'}}"
            )
            raise HTTPException(
                status_code=404,
                detail="Collection not found",
            )

        logger.info(
            "[CollectionCrud.read_one] Retrieved collection | "
            f"{{'project_id': '{self.project_id}', 'collection_id': '{collection_id}'}}"
        )
        return collection

    def read_all(self):
        statement = select(Collection).where(
            and_(
                Collection.project_id == self.project_id,
                Collection.deleted_at.is_(None),
            )
        )

        collections = self.session.exec(statement).all()
        return collections

    @ft.singledispatchmethod
    def delete(self, model, remote):  # remote should be an OpenAICrud
        try:
            raise TypeError(type(model))
        except TypeError as err:
            logger.error(
                f"[CollectionCrud.delete] Invalid model type | {{'model_type': '{type(model).__name__}'}}",
                exc_info=True,
            )
            raise

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

        for coll in self.session.exec(statement):
            self.delete(coll, remote)
        self.session.refresh(model)
        logger.info(
            f"[CollectionCrud.delete] Document deletion from collections completed | {{'document_id': '{model.id}'}}"
        )

        return model
