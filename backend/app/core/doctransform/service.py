import tempfile
import shutil
import logging
from pathlib import Path
from uuid import uuid4, UUID

from fastapi import BackgroundTasks, UploadFile
from tenacity import retry, wait_exponential, stop_after_attempt
from sqlmodel import Session
from starlette.datastructures import Headers

from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.crud.document import DocumentCrud
from app.models.document import Document
from app.models.doc_transformation_job import TransformationStatus
from app.models import User
from app.core.cloud import AmazonCloudStorage
from app.api.deps import CurrentUser
from app.core.doctransform.registry import convert_document, FORMAT_TO_EXTENSION
from app.core.db import engine

logger = logging.getLogger(__name__)

def start_job(
    db: Session,
    current_user: CurrentUser,
    source_document_id: UUID,
    transformer_name: str,
    target_format: str,
    background_tasks: BackgroundTasks,
) -> UUID:
    logger.debug(f"start_job called | source_document_id={source_document_id} | transformer_name={transformer_name} | target_format={target_format} | user_id={current_user.id}")
    job_crud = DocTransformationJobCrud(db)
    job = job_crud.create(source_document_id=source_document_id)
    logger.debug(f"Job created | job_id={job.id}")
    
    # Extract the user ID before passing to background task
    user_id = current_user.id
    background_tasks.add_task(execute_job, user_id, job.id, transformer_name, target_format)
    logger.info(f"[start_job] Job scheduled for document transformation | id: {job.id}, user_id: {user_id}")
    return job.id

@retry(wait=wait_exponential(multiplier=5, min=5, max=10), stop=stop_after_attempt(3))
def execute_job(
    user_id: int,
    job_id: UUID,
    transformer_name: str,
    target_format: str,
):
    try:
        with Session(engine) as db:
            logger.debug(f"execute_job started | job_id={job_id} | transformer_name={transformer_name} | target_format={target_format} | user_id={user_id}")
            job_crud = DocTransformationJobCrud(db)
            doc_crud = DocumentCrud(db, user_id)

            logger.debug(f"Marking job as PROCESSING | job_id={job_id}")
            job_crud.update_status(job_id, TransformationStatus.PROCESSING)

            # fetch source document
            job = job_crud.read_one(job_id)
            logger.debug(f"Fetched job | job_id={job_id} | source_document_id={job.source_document_id}")
            source_doc = doc_crud.read_one(job.source_document_id)
            logger.debug(f"Fetched source document | doc_id={source_doc.id}")

            current_user = User(id=user_id)
            
            # download source file to temp
            storage = AmazonCloudStorage(current_user)
            logger.debug(f"Streaming source document from storage | url={source_doc.object_store_url}")
            body = storage.stream(source_doc.object_store_url)
            tmp_dir = Path(tempfile.mkdtemp())
            tmp_in = tmp_dir / f"{source_doc.id}"
            with open(tmp_in, "wb") as f:
                shutil.copyfileobj(body, f)
            logger.debug(f"Downloaded source document to temp file | path={tmp_in}")

            # transform document
            logger.debug(f"Converting document | path={tmp_in} | transformer={transformer_name}")
            transformed_text = convert_document(tmp_in, transformer_name)
            logger.debug(f"Document transformed | length={len(transformed_text)}")

            # write transformed output with appropriate extension
            fname_no_ext = Path(source_doc.fname).stem
            target_extension = FORMAT_TO_EXTENSION.get(target_format, f".{target_format}")
            transformed_doc_id = uuid4()
            tmp_out = tmp_dir / f"<transformed>{fname_no_ext}{target_extension}"
            tmp_out.write_text(transformed_text)
            logger.debug(f"Transformed output written to temp file | path={tmp_out}")

            # Determine content type based on target format
            content_type_map = {
                "markdown": "text/markdown",
                "text": "text/plain",
                "html": "text/html",
            }
            content_type = content_type_map.get(target_format, "text/plain")

            # upload transformed file and create document record
            with open(tmp_out, "rb") as fobj:
                file_upload = UploadFile(
                    filename=tmp_out.name,
                    file=fobj,
                    headers=Headers({"content-type": content_type}),
                )
                dest = storage.put(file_upload, Path(str(transformed_doc_id)))
            logger.debug(f"Transformed file uploaded | dest={dest}")

            # create new Document record
            new_doc = Document(
                id=transformed_doc_id,
                owner_id=user_id,
                fname=tmp_out.name,
                object_store_url=str(dest),
                source_document_id=source_doc.id,
            )
            created = DocumentCrud(db, user_id).update(new_doc)
            logger.debug(f"New document record created | doc_id={created.id}")

            # mark completed
            job_crud.update_status(job_id, TransformationStatus.COMPLETED, transformed_document_id=created.id)
            logger.debug(f"Job marked as COMPLETED | job_id={job_id}")

    except Exception as e:
        logger.error(f"Transformation job failed | job_id={job_id} | error={e}", exc_info=True)
        try:
            with Session(engine) as db:
                job_crud = DocTransformationJobCrud(db)
                job_crud.update_status(job_id, TransformationStatus.FAILED, error_message=str(e))
        except Exception as db_error:
            logger.error(f"Failed to update job status to FAILED | job_id={job_id} | db_error={db_error}")
        raise