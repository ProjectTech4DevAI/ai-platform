from sqlmodel import Session

from app.models import Document, Collection


class DocumentCollectionCrud:
    def __init__(self, session: Session):
        self.session = session

    def update(self, collection: Collection, documents: list[Document]):
        pass
