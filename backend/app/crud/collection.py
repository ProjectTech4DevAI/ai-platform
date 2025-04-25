import functools as ft
from uuid import UUID
from typing import Optional

from sqlmodel import Session, func, select, and_

from app.models import Document, Collection, DocumentCollection
from app.core.util import now

from .document_collection import DocumentCollectionCrud


class CollectionCrud:
    def __init__(self, session: Session, owner_id: UUID):
        self.session = session
        self.owner_id = owner_id

    def _exists(self, collection: Collection):
        n = (
            self.session.query(func.count(Collection.id))
            .filter(
                Collection.llm_service_id == collection.llm_service_id,
                Collection.llm_service_name == collection.llm_service_name,
            )
            .scalar()
        )

        return bool(n)

    def create(self, collection: Collection, documents: list[Document]):
        if self._exists(collection):
            raise FileExistsError("Collection already present")

        collection = self.update(collection)
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

        return self.session.exec(statement).one()

    def read_many(
        self,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.deleted_at.is_(None),
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

    def update(self, collection: Collection):
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

    @ft.singledispatchmethod
    def delete(self, model, remote):  # remote should be an OpenAICrud
        raise TypeError(type(model))

    @delete.register
    def _(self, model: Collection, remote):
        remote.delete(model.llm_service_id)
        model.deleted_at = now()
        return self.update(model)

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
            self.delete(c, remote)
        self.session.refresh(model)

        return model
