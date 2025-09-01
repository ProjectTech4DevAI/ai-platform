import logging
from uuid import UUID
from typing import List, Optional
from sqlmodel import Session, select, and_, join
from app.crud import DocumentCrud
from app.models import DocTransformationJob, TransformationStatus
from app.models.document import Document
from app.core.util import now
from app.core.exception_handlers import HTTPException

logger = logging.getLogger(__name__)

class DocTransformationJobCrud:
    def __init__(self, session: Session, project_id: int):
        self.session = session
        self.project_id = project_id

    def create(self, source_document_id: UUID) -> DocTransformationJob:
        # Ensure the source document exists and is not deleted
        DocumentCrud(self.session, self.project_id).read_one(source_document_id)

        job = DocTransformationJob(source_document_id=source_document_id)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        logger.info(f"[DocTransformationJobCrud.create] Created new transformation job | id: {job.id}, source_document_id: {source_document_id}")
        return job

    def read_one(self, job_id: UUID) -> DocTransformationJob:
        statement = (
            select(DocTransformationJob)
            .join(Document, DocTransformationJob.source_document_id == Document.id)
            .where(
                and_(
                    DocTransformationJob.id == job_id,
                    Document.project_id == self.project_id,
                    Document.is_deleted.is_(False)
                )
            )
        )
        
        job = self.session.exec(statement).one_or_none()
        if not job:
            logger.warning(f"[DocTransformationJobCrud.read_one] Job not found or Document is deleted | id: {job_id}, project_id: {self.project_id}")
            raise HTTPException(status_code=404, detail="Transformation job not found")
        return job

    def read_each(self, job_ids: set[UUID]) -> list[DocTransformationJob]:
        statement = (
            select(DocTransformationJob)
            .join(Document, DocTransformationJob.source_document_id == Document.id)
            .where(
                and_(
                    DocTransformationJob.id.in_(list(job_ids)),
                    Document.project_id == self.project_id,
                    Document.is_deleted.is_(False)
                )
            )
        )

        jobs = self.session.exec(statement).all()
        return jobs

    def update_status(
        self,
        job_id: UUID,
        status: TransformationStatus,
        *,
        error_message: Optional[str] = None,
        transformed_document_id: Optional[UUID] = None,
    ) -> DocTransformationJob:
        job = self.read_one(job_id)
        job.status = status
        job.updated_at = now()
        if error_message is not None:
            job.error_message = error_message
        if transformed_document_id is not None:
            job.transformed_document_id = transformed_document_id

        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        logger.info(f"[DocTransformationJobCrud.update_status] Updated job status | id: {job.id}, status: {status}")
        return job
