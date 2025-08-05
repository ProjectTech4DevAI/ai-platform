import logging
from uuid import UUID
from typing import List, Optional
from sqlmodel import Session, select
from app.models.doc_transformation_job import DocTransformationJob, TransformationStatus
from app.core.util import now
from app.core.exception_handlers import HTTPException

logger = logging.getLogger(__name__)

class DocTransformationJobCrud:
    def __init__(self, session: Session):
        self.session = session

    def create(self, source_document_id: UUID) -> DocTransformationJob:
        job = DocTransformationJob(source_document_id=source_document_id)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def read_one(self, job_id: UUID) -> DocTransformationJob:
        job = self.session.get(DocTransformationJob, job_id)
        if not job:
            logger.warning(f"[DocTransformationJobCrud.read_one] Job not found | id: {job_id}")
            raise HTTPException(status_code=404, detail="Transformation job not found")
        return job

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
        return job

    def read_many(self, skip: int = 0, limit: int = 100) -> List[DocTransformationJob]:
        statement = select(DocTransformationJob).offset(skip).limit(limit)
        return self.session.exec(statement).all()
