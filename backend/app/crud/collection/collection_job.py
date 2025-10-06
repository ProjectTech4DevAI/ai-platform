from uuid import UUID
import logging
from typing import List

from fastapi import HTTPException
from sqlmodel import Session, select, and_

from app.models.collection_job import (
    CollectionJob,
    CollectionJobUpdate,
    CollectionJobCreate,
)
from app.core.util import now


logger = logging.getLogger(__name__)


class CollectionJobCrud:
    def __init__(self, session: Session, project_id: int):
        self.session = session
        self.project_id = project_id

    def read_one(self, job_id: UUID) -> CollectionJob:
        """Retrieve a single collection job by its id; 404 if not found."""
        statement = select(CollectionJob).where(
            and_(
                CollectionJob.project_id == self.project_id,
                CollectionJob.id == job_id,
            )
        )
        collection_job = self.session.exec(statement).first()
        if collection_job is None:
            logger.error(
                "[CollectionJobCrud.read_one] Collection job not found | "
                f"{{'project_id': '{self.project_id}', 'job_id': '{job_id}'}}"
            )
            raise HTTPException(
                status_code=404,
                detail="Collection job not found",
            )

        logger.info(
            "[CollectionJobCrud.read_one] Retrieved collection job | "
            f"{{'job_id': '{job_id}'}}"
        )
        return collection_job

    def read_all(self) -> List[CollectionJob]:
        """Retrieve all collection jobs for a given project."""
        statement = select(CollectionJob).where(
            CollectionJob.project_id == self.project_id
        )
        collection_jobs = self.session.exec(statement).all()
        logger.info(
            f"[CollectionJobCrud.read_all] Retrieved all collection jobs for project | {{'project_id': '{self.project_id}', 'count': {len(collection_jobs)}}}"
        )
        return collection_jobs

    def update(
        self, job_id: UUID, collection_job: CollectionJobUpdate
    ) -> CollectionJob:
        """Update an existing collection job."""
        collection_job = self.read_one(job_id)

        collection_job.updated_at = now()
        self.session.add(collection_job)
        self.session.commit()
        self.session.refresh(collection_job)
        logger.info(
            f"[CollectionJobCrud._update] Collection job updated successfully | {{'collection_job_id': '{collection_job.id}'}}"
        )

        return collection_job

    def create(self, collection_job: CollectionJobCreate) -> CollectionJob:
        """Create a new collection job."""
        try:
            self.session.add(collection_job)
            self.session.commit()
            self.session.refresh(collection_job)
            logger.info(
                f"[CollectionJobCrud.create] Collection job created successfully | {{'collection_job_id': '{collection_job.id}'}}"
            )

        except Exception as e:
            logger.error(
                f"[CollectionJobCrud.create] Error during job creation: {str(e)}",
                exc_info=True,
            )
            raise

        return collection_job
