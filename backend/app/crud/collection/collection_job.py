from datetime import datetime
import logging

from app.models.collection_job import CollectionJob, CollectionJobUpdate


from sqlmodel import Session, func, select, and_

logger = logging.getLogger(__name__)


class CollectionJobCrud:
    def __init__(self, session: Session, project_id: int):
        self.session = session
        self.project_id = project_id

    def _update(self, collection_job: CollectionJobUpdate):
        """Update an existing collection job."""
        if collection_job.project_id != self.project_id:
            err = f"Invalid collection job ownership: owner_project={self.project_id} attempter={collection_job.project_id}"
            try:
                raise PermissionError(err)
            except PermissionError as e:
                logger.error(
                    f"[CollectionJobCrud._update] Permission error | {{'collection_job_id': '{collection_job.id}', 'error': '{str(e)}'}}",
                    exc_info=True,
                )
                raise

        collection_job.updated_at = datetime.utcnow()
        self.session.add(collection_job)
        self.session.commit()
        self.session.refresh(collection_job)
        logger.info(
            f"[CollectionJobCrud._update] Collection job updated successfully | {{'collection_job_id': '{collection_job.id}'}}"
        )

        return collection_job

    def create(self, collection_job: CollectionJob):
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

    def read_one(self, task_id: str) -> CollectionJob:
        """Retrieve a single collection job by its task_id."""
        statement = select(CollectionJob).where(
            and_(
                CollectionJob.project_id == self.project_id,
                CollectionJob.id == task_id,
            )
        )
        collection_job = self.session.exec(statement).one()
        logger.info(
            f"[CollectionJobCrud.read_one] Retrieved collection job | {{'task_id': '{task_id}'}}"
        )
        return collection_job

    def read_all(self):
        """Retrieve all collection jobs for a given project."""
        statement = select(CollectionJob).where(
            and_(
                CollectionJob.project_id == self.project_id,
                CollectionJob.updated_at.isnot(
                    None
                ),  # Exclude any jobs that have been deleted
            )
        )
        collection_jobs = self.session.exec(statement).all()
        logger.info(
            f"[CollectionJobCrud.read_all] Retrieved all collection jobs for project | {{'project_id': '{self.project_id}', 'count': {len(collection_jobs)}}}"
        )
        return collection_jobs
