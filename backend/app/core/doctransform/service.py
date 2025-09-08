import tempfile
import shutil
import logging
from pathlib import Path
from uuid import uuid4, UUID

from fastapi import UploadFile
from tenacity import retry, wait_exponential, stop_after_attempt
from sqlmodel import Session
from starlette.datastructures import Headers

from app.crud.doc_transformation_job import DocTransformationJobCrud
from app.crud.document import DocumentCrud
from app.models.document import Document
from app.models.doc_transformation_job import TransformationStatus
from app.api.deps import CurrentUserOrgProject
from app.core.cloud import get_cloud_storage
from app.core.doctransform.registry import convert_document, FORMAT_TO_EXTENSION
from app.core.db import engine
from app.celery.utils import start_low_priority_job

logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    current_user: CurrentUserOrgProject,
    source_document_id: UUID,
    transformer_name: str,
    target_format: str,
) -> UUID:
    job_crud = DocTransformationJobCrud(session=db, project_id=current_user.project_id)
    job = job_crud.create(source_document_id=source_document_id)

    # Extract the project ID before passing to Celery task
    project_id = current_user.project_id
    
    # Start the low priority Celery task, passing job_id
    task_id = start_low_priority_job(
        function_path="app.core.doctransform.service.execute_job",
        project_id=project_id,
        job_id=str(job.id),
        transformer_name=transformer_name,
        target_format=target_format,
    )
    
    # Note: We don't update task_id here to avoid race condition
    # execute_job will update both task_id and status atomically
    
    logger.info(
        f"[start_job] Job scheduled for document transformation | id: {job.id}, project_id: {project_id}, task_id: {task_id}"
    )
    return job.id


@retry(wait=wait_exponential(multiplier=5, min=5, max=10), stop=stop_after_attempt(3))
def execute_job(
    project_id: int,
    job_id: str,
    task_id: str,
    task_instance,
    transformer_name: str,
    target_format: str,
):
    tmp_dir: Path | None = None
    job_uuid = UUID(job_id)
    
    try:
        logger.info(
            f"[execute_job started] Transformation Job started | job_id={job_id} | task_id={task_id} | transformer_name={transformer_name} | target_format={target_format} | project_id={project_id}"
        )

        # Update job status to PROCESSING and set task_id atomically
        with Session(engine) as db:
            job_crud = DocTransformationJobCrud(session=db, project_id=project_id)
            # This single database call updates both status and task_id atomically
            job = job_crud.update_status(
                job_uuid, 
                TransformationStatus.PROCESSING,
                task_id=task_id
            )

            doc_crud = DocumentCrud(session=db, project_id=project_id)

            source_doc = doc_crud.read_one(job.source_document_id)

            source_doc_id = source_doc.id
            source_doc_fname = source_doc.fname
            source_doc_object_store_url = source_doc.object_store_url

            storage = get_cloud_storage(session=db, project_id=project_id)

        # Download and transform document
        body = storage.stream(source_doc_object_store_url)
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_in = tmp_dir / f"{source_doc_id}"
        with open(tmp_in, "wb") as f:
            shutil.copyfileobj(body, f)

        # prepare output file path
        fname_no_ext = Path(source_doc_fname).stem
        target_extension = FORMAT_TO_EXTENSION.get(target_format, f".{target_format}")
        transformed_doc_id = uuid4()
        tmp_out = tmp_dir / f"<transformed>{fname_no_ext}{target_extension}"

        # transform document - now returns the output file path
        convert_document(tmp_in, tmp_out, transformer_name)

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
            job_crud.update_status(
                job_uuid,
                TransformationStatus.COMPLETED,
                transformed_document_id=created.id,
            )

            logger.info(
                f"[execute_job] Doc Transformation job completed | job_id={job_id} | task_id={task_id} | transformed_doc_id={created.id} | project_id={project_id}"
            )

    except Exception as e:
        logger.error(
            f"Transformation job failed | job_id={job_id} | task_id={task_id} | error={e}", exc_info=True
        )
        try:
            with Session(engine) as db:
                job_crud = DocTransformationJobCrud(session=db, project_id=project_id)
                job_crud.update_status(
                    job_uuid, 
                    TransformationStatus.FAILED, 
                    error_message=str(e),
                    task_id=task_id  # Ensure task_id is set even on failure
                )
                logger.info(
                    f"[execute_job] Doc Transformation job failed | job_id={job_id} | task_id={task_id} | error={e}"
                )
        except Exception as db_error:
            logger.error(
                f"Failed to update job status to FAILED | job_id={job_id} | task_id={task_id} | db_error={db_error}"
            )
        raise
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir)
