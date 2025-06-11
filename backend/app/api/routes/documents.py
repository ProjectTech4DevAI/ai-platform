from uuid import UUID, uuid4
from typing import List
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi import Path as FastPath

from sqlalchemy.exc import NoResultFound, MultipleResultsFound, SQLAlchemyError

from app.crud import DocumentCrud, CollectionCrud
from app.models import Document
from app.utils import APIResponse
from app.api.deps import CurrentUser, SessionDep
from app.core.util import raise_from_unknown
from app.core.cloud import AmazonCloudStorage, CloudStorageError
from app.crud.rag import OpenAIAssistantCrud
from app.core.exception_handlers import (
    NotFoundException,
    ServiceUnavailableException,
    DatabaseException,
    UnhandledAppException,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/list", response_model=APIResponse[List[Document]])
def list_docs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
):
    crud = DocumentCrud(session, current_user.id)
    try:
        data = crud.read_many(skip, limit)
    except (ValueError, SQLAlchemyError) as err:
        raise DatabaseException(str(err))
    except Exception as err:
        raise UnhandledAppException(str(err))

    return APIResponse.success_response(data)


@router.post("/upload", response_model=APIResponse[Document])
def upload_doc(
    session: SessionDep,
    current_user: CurrentUser,
    src: UploadFile = File(...),
):
    storage = AmazonCloudStorage(current_user)
    document_id = uuid4()
    try:
        object_store_url = storage.put(src, Path(str(document_id)))
    except CloudStorageError as err:
        raise ServiceUnavailableException(str(err))
    except Exception as err:
        raise UnhandledAppException(str(err))

    crud = DocumentCrud(session, current_user.id)
    document = Document(
        id=document_id,
        fname=src.filename,
        object_store_url=str(object_store_url),
    )

    try:
        data = crud.update(document)
    except SQLAlchemyError as err:
        raise DatabaseException(str(err))
    except Exception as err:
        raise UnhandledAppException(str(err))

    return APIResponse.success_response(data)


@router.get("/remove/{doc_id}", response_model=APIResponse[Document])
def remove_doc(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID = Path(description="Document to delete"),
):
    a_crud = OpenAIAssistantCrud()
    (d_crud, c_crud) = (
        x(session, current_user.id) for x in (DocumentCrud, CollectionCrud)
    )
    try:
        document = d_crud.delete(doc_id)
        data = c_crud.delete(document, a_crud)
    except NoResultFound as err:
        raise NotFoundException(str(err))
    except Exception as err:
        raise UnhandledAppException(str(err))

    return APIResponse.success_response(data)


@router.get("/info/{doc_id}", response_model=APIResponse[Document])
def doc_info(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID = FastPath(description="Document to retrieve"),
):
    crud = DocumentCrud(session, current_user.id)
    try:
        data = crud.read_one(doc_id)
    except NoResultFound as err:
        raise NotFoundException(str(err))
    except MultipleResultsFound as err:
        raise ServiceUnavailableException(str(err))
    except Exception as err:
        raise UnhandledAppException(str(err))

    return APIResponse.success_response(data)
