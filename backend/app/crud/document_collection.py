import logging
from typing import Optional

from sqlmodel import Session, select

from app.models import Document, Collection, DocumentCollection

logger = logging.getLogger(__name__)


class DocumentCollectionCrud:
    def __init__(self, session: Session):
        self.session = session
        logger.info(
            f"[DocumentCollectionCrud.init] Initialized DocumentCollectionCrud | {{'session': 'active'}}"
        )

    def create(self, collection: Collection, documents: list[Document]):
        logger.info(
            f"[DocumentCollectionCrud.create] Starting creation of document-collection associations | {{'collection_id': '{collection.id}', 'document_count': {len(documents)}}}"
        )
        document_collection = []
        for d in documents:
            dc = DocumentCollection(
                document_id=d.id,
                collection_id=collection.id,
            )
            logger.info(
                f"[DocumentCollectionCrud.create] Adding document to collection | {{'collection_id': '{collection.id}', 'document_id': '{d.id}'}}"
            )
            document_collection.append(dc)

        logger.info(
            f"[DocumentCollectionCrud.create] Saving document-collection associations | {{'collection_id': '{collection.id}', 'association_count': {len(document_collection)}}}"
        )
        self.session.bulk_save_objects(document_collection)
        self.session.commit()
        self.session.refresh(collection)
        logger.info(
            f"[DocumentCollectionCrud.create] Document-collection associations created successfully | {{'collection_id': '{collection.id}'}}"
        )

    def read(
        self,
        collection: Collection,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        logger.info(
            f"[DocumentCollectionCrud.read] Retrieving documents for collection | {{'collection_id': '{collection.id}', 'skip': {skip}, 'limit': {limit}}}"
        )
        statement = (
            select(Document)
            .join(
                DocumentCollection,
                DocumentCollection.document_id == Document.id,
            )
            .where(DocumentCollection.collection_id == collection.id)
        )
        if skip is not None:
            if skip < 0:
                logger.error(
                    f"[DocumentCollectionCrud.read] Invalid skip value | {{'collection_id': '{collection.id}', 'skip': {skip}, 'error': 'Negative skip'}}"
                )
                raise ValueError(f"Negative skip: {skip}")
            statement = statement.offset(skip)
            logger.info(
                f"[DocumentCollectionCrud.read] Applied skip offset | {{'collection_id': '{collection.id}', 'skip': {skip}}}"
            )
        if limit is not None:
            if limit < 0:
                logger.error(
                    f"[DocumentCollectionCrud.read] Invalid limit value | {{'collection_id': '{collection.id}', 'limit': {limit}, 'error': 'Negative limit'}}"
                )
                raise ValueError(f"Negative limit: {limit}")
            statement = statement.limit(limit)
            logger.info(
                f"[DocumentCollectionCrud.read] Applied limit | {{'collection_id': '{collection.id}', 'limit': {limit}}}"
            )

        documents = self.session.exec(statement).all()
        logger.info(
            f"[DocumentCollectionCrud.read] Documents retrieved successfully | {{'collection_id': '{collection.id}', 'document_count': {len(documents)}}}"
        )
        return documents
