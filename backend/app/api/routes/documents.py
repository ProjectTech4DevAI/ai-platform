from uuid import UUID, uuid4

from fastapi import APIRouter, File, UploadFile, HTTPException

from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from app.crud import DocumentCrud
from app.models import Document, DocumentList
from app.api.deps import CurrentUser, SessionDep
from app.core.cloud import AmazonCloudStorage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/ls", response_model=DocumentList)
def list_docs(
        session: SessionDep,
        current_user: CurrentUser,
        skip: int = 0,
        limit: int = 100,
):
    crud = DocumentCrud(session, current_user.id)
    try:
        return crud.read_many(skip, limit)
    except ValueError as err:
        raise HTTPException(status_code=500, detail=str(err))

@router.post("/cp")
def upload_doc(
        session: SessionDep,
        current_user: CurrentUser,
        src: UploadFile = File(...),
):
    storage = AmazonCloudStorage(current_user)
    basename = uuid4()
    try:
        object_store_url = storage.put(src, str(basename))
    except ConnectionError as err:
        raise HTTPException(status_code=500, detail=str(err))

    crud = DocumentCrud(session, current_user.id)
    document = Document(
        id=basename,
        fname=src.filename,
        object_store_url=str(object_store_url)
    )

    return crud.update(document)

@router.get("/rm/{doc_id}")
def delete_doc(
        session: SessionDep,
        current_user: CurrentUser,
        doc_id: UUID,
):
    crud = DocumentCrud(session, current_user.id)
    try:
        return crud.delete(doc_id)
    except NoResultFound as err:
        raise HTTPException(status_code=404, detail=str(err))

    # TODO: perform delete on the collection

@router.get("/stat/{doc_id}", response_model=Document)
def doc_info(
        session: SessionDep,
        current_user: CurrentUser,
        doc_id: UUID,
):
    crud = DocumentCrud(session, current_user.id)
    try:
        return crud.read_one(doc_id)
    except NoResultFound as err:
        raise HTTPException(status_code=404, detail=str(err))
    except MultipleResultsFound as err:
        raise HTTPException(status_code=500, detail=str(err))
