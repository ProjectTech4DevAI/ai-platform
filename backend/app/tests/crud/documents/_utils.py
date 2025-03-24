import functools as ft
from uuid import UUID
from pathlib import Path

from sqlmodel import Session, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.sqlite import insert

from app.crud import DocumentCrud
from app.core.config import settings
from app.crud.user import get_user_by_email
from app.models import Document, UserCreate

class Constants:
    n_documents = 10

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

def mk_document(owner_id, index=0):
    doc_id = int_to_uuid(index)

    args = str(doc_id).split('-')
    fname = Path('/', *args).with_suffix('.xyz')
    return Document(
        id=doc_id,
        owner_id=owner_id,
        fname=fname.name,
        object_store_url=fname.as_uri(),
    )

def insert_documents(session: Session, n: int):
    owner_id = get_user_id_by_email(session)

    crud = DocumentCrud(session)
    for i in range(n):
        document = mk_document(owner_id, i)

        session.add(document)
        session.commit()
        session.refresh(document)

        yield document

def insert_document(session: Session):
    (document, ) = insert_documents(session, 1)
    return document
