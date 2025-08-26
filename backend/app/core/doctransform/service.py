import tempfile
import shutil
import logging
from pathlib import Path
from uuid import uuid4, UUID

from app.crud.project import get_project_by_id
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
from app.api.deps import CurrentUserOrgProject
from app.core.doctransform.registry import convert_document, FORMAT_TO_EXTENSION
from app.core.db import engine

logger = logging.getLogger(__name__)

def start_job(
    db: Session,
    current_user: CurrentUserOrgProject,
    source_document_id: UUID,
    transformer_name: str,
    target_format: str,
    background_tasks: BackgroundTasks,
) -> UUID:
    job_crud = DocTransformationJobCrud(session=db, project_id=current_user.project_id)
    job = job_crud.create(source_document_id=source_document_id)
    
    # Extract the project ID before passing to background task
    project_id = current_user.project_id
    background_tasks.add_task(execute_job, project_id, job.id, transformer_name, target_format)
    logger.info(f"[start_job] Job scheduled for document transformation | id: {job.id}, project_id: {project_id}")
    return job.id

@retry(wait=wait_exponential(multiplier=5, min=5, max=10), stop=stop_after_attempt(3))
def execute_job(
    project_id: int,
    job_id: UUID,
    transformer_name: str,
    target_format: str,
):
    try:
        logger.info(f"[execute_job started] Transformation Job started | job_id={job_id} | transformer_name={transformer_name} | target_format={target_format} | project_id={project_id}")

        # Update job status to PROCESSING and fetch source document info
        with Session(engine) as db:
            job_crud = DocTransformationJobCrud(session=db, project_id=project_id)
            job = job_crud.update_status(job_id, TransformationStatus.PROCESSING)

            doc_crud = DocumentCrud(session=db, project_id=project_id)
            
            source_doc = doc_crud.read_one(job.source_document_id)
            
            source_doc_id = source_doc.id
            source_doc_fname = source_doc.fname
            source_doc_object_store_url = source_doc.object_store_url

            project = get_project_by_id(session=db, project_id=project_id)
            project_storage_path = project.storage_path

        # Download and transform document
        storage = AmazonCloudStorage(project_id=project_id)
        body = storage.stream(source_doc_object_store_url)
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_in = tmp_dir / f"{source_doc_id}"
        with open(tmp_in, "wb") as f:
            shutil.copyfileobj(body, f)

        # transform document
        transformed_text = convert_document(tmp_in, transformer_name)

        # write transformed output with appropriate extension
        fname_no_ext = Path(source_doc_fname).stem
        target_extension = FORMAT_TO_EXTENSION.get(target_format, f".{target_format}")
        transformed_doc_id = uuid4()
        tmp_out = tmp_dir / f"<transformed>{fname_no_ext}{target_extension}"
        tmp_out.write_text(transformed_text)

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
            key = Path(str(project_storage_path), str(transformed_doc_id))
            dest = storage.put(file_upload, key)

        # create new Document record
        with Session(engine) as db:
            new_doc = Document(
                id=transformed_doc_id,
                project_id=project_id,
                fname=tmp_out.name,
                object_store_url=str(dest),
                source_document_id=source_doc_id,
            )
            created = DocumentCrud(db, project_id).update(new_doc)

            job_crud = DocTransformationJobCrud(session=db, project_id=project_id)
            job_crud.update_status(job_id, TransformationStatus.COMPLETED, transformed_document_id=created.id)

            logger.info(f"[execute_job] Doc Transformation job completed | job_id={job_id} | transformed_doc_id={created.id} | project_id={project_id}")

    except Exception as e:
        logger.error(f"Transformation job failed | job_id={job_id} | error={e}", exc_info=True)
        try:
            with Session(engine) as db:
                job_crud = DocTransformationJobCrud(session=db, project_id=project_id)
                job_crud.update_status(job_id, TransformationStatus.FAILED, error_message=str(e))
                logger.info(f"[execute_job] Doc Transformation job failed | job_id={job_id} | error={e}")
        except Exception as db_error:
            logger.error(f"Failed to update job status to FAILED | job_id={job_id} | db_error={db_error}")
        raise
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir)
