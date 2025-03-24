import functools as ft
from uuid import UUID
from pathlib import Path

import pytest
from sqlmodel import Session, delete

from app.core.config import settings
from app.crud.user import get_user_by_email
from app.models import Document

@ft.cache
def get_user_id_by_email(session: Session):
    user = get_user_by_email(session=session, email=settings.FIRST_SUPERUSER)
    return user.id

@ft.cache
def int_to_uuid(value):
    return UUID(int=value)

def rm_documents(session: Session):
    session.exec(delete(Document))
    session.commit()

def insert_documents(session: Session, n: int):
    documents = DocumentMaker(session)
    for (_, doc) in zip(range(n), documents):
        session.add(doc)
        session.commit()
        session.refresh(doc)
        yield doc

def insert_document(session: Session):
    (document, ) = insert_documents(session, 1)
    return document

@pytest.fixture(scope='class')
def clean_db_fixture(db: Session):
    rm_documents(db)
    yield
    rm_documents(db)

class Constants:
    n_documents = 10

class DocumentMaker:
    def __init__(self, session: Session):
        self.owner_id = get_user_id_by_email(session)
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        doc_id = self.get_and_increment()
        args = str(doc_id).split('-')
        fname = Path('/', *args).with_suffix('.xyz')

        return Document(
            id=doc_id,
            owner_id=self.owner_id,
            fname=fname.name,
            object_store_url=fname.as_uri(),
        )

    def get_and_increment(self):
        doc_id = int_to_uuid(self.index)
        self.index += 1
        return doc_id
