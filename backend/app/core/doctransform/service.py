import tempfile
import shutil
import logging
from pathlib import Path
from uuid import uuid4, UUID

from fastapi import BackgroundTasks, UploadFile
from tenacity import retry, wait_exponential, stop_after_attempt
from sqlmodel import Session, select

from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.crud.document import DocumentCrud
from app.models.document import Document
from app.models.doc_transformation_job import TransformationStatus
from app.core.util import now
from app.core.cloud import AmazonCloudStorage
from app.api.deps import CurrentUser
from app.core.doctransform.registry import convert_document

logger = logging.getLogger(__name__)

def start_job(
    db: Session,
    current_user: CurrentUser,
    source_document_id: UUID,
    transformer_name: str,
    background_tasks: BackgroundTasks,
) -> UUID:
    job_crud = DocTransformationJobCrud(db)
    job = job_crud.create(source_document_id=source_document_id)
    background_tasks.add_task(execute_job, db, current_user, job.id, transformer_name)
    return job.id

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def execute_job(
    db: Session,
    current_user: CurrentUser,
    job_id: UUID,
    transformer_name: str,
):
    job_crud = DocTransformationJobCrud(db)
    doc_crud = DocumentCrud(db, current_user.id)

    try:
        # mark processing
        job_crud.update_status(job_id, TransformationStatus.PROCESSING)

        # fetch source document
        job = job_crud.read_one(job_id)
        source_doc = doc_crud.read_one(job.source_document_id)

        # download source file to temp
        storage = AmazonCloudStorage(current_user)
        body = storage.stream(source_doc.object_store_url)
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_in = tmp_dir / f"{source_doc.id}"
        with open(tmp_in, "wb") as f:
            shutil.copyfileobj(body, f)

        # transform to text
        transformed_text = convert_document(tmp_in, transformer_name)

        # write transformed output
        tmp_out = tmp_dir / f"{uuid4()}.txt"
        tmp_out.write_text(transformed_text)

        # upload transformed file
        with open(tmp_out, "rb") as fobj:
            upload_file = UploadFile(filename=tmp_out.name, file=fobj, content_type="text/plain")
            dest = storage.put(upload_file, Path(str(uuid4())))

        # create new Document record
        new_doc = Document(
            id=uuid4(),
            owner_id=current_user.id,
            fname=upload_file.filename,
            object_store_url=str(dest),
            source_document_id=source_doc.id,
        )
        created = DocumentCrud(db, current_user.id).update(new_doc)

        # mark completed
        job_crud.update_status(job_id, TransformationStatus.COMPLETED, transformed_document_id=created.id)

    except Exception as e:
        logger.error(f"Transformation job failed | job_id={job_id} | error={e}", exc_info=True)
        job_crud.update_status(job_id, TransformationStatus.FAILED, error_message=str(e))
        raise
    