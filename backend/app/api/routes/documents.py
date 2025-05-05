import warnings
from uuid import UUID, uuid4
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, Query

from sqlalchemy.exc import NoResultFound, MultipleResultsFound, SQLAlchemyError

from app.crud import DocumentCrud
from app.models import Document
from app.utils import APIResponse
from app.api.deps import CurrentUser, SessionDep
from app.core.cloud import AmazonCloudStorage, CloudStorageError

router = APIRouter(prefix="/documents", tags=["documents"])


def raise_from_unknown(error: Exception):
    warnings.warn(
        'Unexpected exception "{}": {}'.format(
            type(error).__name__,
            error,
        )
    )
    raise HTTPException(status_code=500, detail=str(error))


@router.get("/ls", response_model=APIResponse[List[Document]],include_in_schema=False)
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
        raise HTTPException(status_code=403, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    return APIResponse.success_response(data)


@router.post("/cp", response_model=APIResponse[Document],include_in_schema=False)
def upload_doc(
    session: SessionDep,
    current_user: CurrentUser,
    src: UploadFile = File(...),
):
    storage = AmazonCloudStorage(current_user)
    basename = uuid4()
    try:
        object_store_url = storage.put(src, str(basename))
    except CloudStorageError as err:
        raise HTTPException(status_code=503, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    crud = DocumentCrud(session, current_user.id)
    document = Document(
        id=basename, fname=src.filename, object_store_url=str(object_store_url)
    )

    try:
        data = crud.update(document)
    except SQLAlchemyError as err:
        raise HTTPException(status_code=403, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    return APIResponse.success_response(data)


@router.get("/rm/{doc_id}", response_model=APIResponse[Document],include_in_schema=False)
def delete_doc(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID,
):
    crud = DocumentCrud(session, current_user.id)
    try:
        data = crud.delete(doc_id)
    except NoResultFound as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    # TODO: perform delete on the collection

    return APIResponse.success_response(data)


@router.get("/stat/{doc_id}", response_model=APIResponse[Document])
def doc_info(
    session: SessionDep,
    current_user: CurrentUser,
    doc_id: UUID,
):
    crud = DocumentCrud(session, current_user.id)
    try:
        data = crud.read_one(doc_id)
    except NoResultFound as err:
        raise HTTPException(status_code=404, detail=str(err))
    except MultipleResultsFound as err:
        raise HTTPException(status_code=503, detail=str(err))
    except Exception as err:
        raise_from_unknown(err)

    return APIResponse.success_response(data)
