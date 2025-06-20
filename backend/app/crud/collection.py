import functools as ft
from uuid import UUID
from typing import Optional
import logging
from sqlmodel import Session, func, select, and_

from app.models import Document, Collection, DocumentCollection
from app.core.util import now

from .document_collection import DocumentCollectionCrud


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
            raise PermissionError(err)

        self.session.add(collection)
        self.session.commit()
        self.session.refresh(collection)

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

        return bool(present)

    def create(
        self, collection: Collection, documents: Optional[list[Document]] = None
    ):
        if self._exists(collection):
            raise FileExistsError("Collection already present")

        # Update or create the collection first
        collection = self._update(collection)

        # Only link documents if present
        if documents:
            dc_crud = DocumentCollectionCrud(self.session)
            dc_crud.create(collection, documents)
        else:
            logging.warning(
                f"No documents provided for collection {collection.id}, skipping DocumentCollection creation."
            )

        return collection

    def read_one(self, collection_id: UUID):
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.id == collection_id,
            )
        )

        return self.session.exec(statement).one()

    def read_all(self):
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.deleted_at.is_(None),
            )
        )

        return self.session.exec(statement).all()

    @ft.singledispatchmethod
    def delete(self, model, remote):  # remote should be an OpenAICrud
        raise TypeError(type(model))

    @delete.register
    def _(self, model: Collection, remote):
        remote.delete(model.llm_service_id)
        model.deleted_at = now()
        return self._update(model)

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

        return model
