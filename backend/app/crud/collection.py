from sqlmodel import Session

from app.models import Document, Collection, DocumentCollection

from app.core.util import now


class CollectionCrud:
    def __init__(self, session: Session, owner_id: UUID):
        self.session = session
        self.owner_id = owner_id

    def exists(self, collection: Collection):
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
        if self.exists(collection):
            raise FileExistsError("Collection already present")

        collection = self.update(collection)
        document_collection = []
        for d in documents:
            dc = DocumentCollection(
                document_id=d.id,
                collection_id=collection.id,
            )
            document_collection.append(dc)

        self.session.bulk_save_objects(document_collection)
        self.session.commit()

        return collection

    def read(self, collection_id: UUID):
        statement = select(Collection).where(
            and_(
                Collection.owner_id == self.owner_id,
                Collection.id == collection_id,
            )
        )

        return self.session.exec(statement).one()

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

    def delete(self, collection_id: UUID):
        collection = self.read(collection_id)
        collection.deleted_at = now()

        return self.update(collection)
