from sqlmodel import Session

from app.models import Collection


class CollectionCrud:
    def __init__(self, session: Session):
        self.session = session

    def create(self, collection: Collection):
        self.session.add(collection)
        self.session.commit()
        self.session.refresh(collection)

        return collection
