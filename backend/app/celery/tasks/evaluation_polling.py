"""
Celery tasks for evaluation batch polling.

This module contains periodic tasks that poll OpenAI batch status
and process completed evaluations.
"""

import asyncio
import logging

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import get_engine
from app.crud.evaluation_processing import poll_all_pending_evaluations
from app.models import Organization

logger = logging.getLogger(__name__)


@shared_task(name="poll_evaluation_batches", bind=True)
def poll_evaluation_batches_task(self):
    """
    Periodic task to poll all pending evaluation batches.

    This task:
    1. Gets all organizations
    2. For each org, polls their pending evaluations
    3. Processes completed batches automatically

    Runs every 60 seconds (configured in celery_app.py beat_schedule)
    """
    logger.info("[poll_evaluation_batches] Starting evaluation batch polling")

    try:
        # Get database session
        engine = get_engine()
        with Session(engine) as session:
            # Get all organizations
            orgs = session.exec(select(Organization)).all()

            if not orgs:
                logger.info("[poll_evaluation_batches] No organizations found")
                return {
                    "status": "success",
                    "organizations_processed": 0,
                    "message": "No organizations to process",
                }

            logger.info(
                f"[poll_evaluation_batches] Found {len(orgs)} organizations to process"
            )

            results = []
            total_processed = 0
            total_failed = 0
            total_still_processing = 0

            # Process each organization
            for org in orgs:
                try:
                    logger.info(
                        f"[poll_evaluation_batches] Processing org_id={org.id} ({org.name})"
                    )

                    # Poll all pending evaluations for this org
                    # Use asyncio.run since poll_all_pending_evaluations is async
                    summary = asyncio.run(
                        poll_all_pending_evaluations(session=session, org_id=org.id)
                    )

                    results.append(
                        {
                            "org_id": org.id,
                            "org_name": org.name,
                            "summary": summary,
                        }
                    )

                    total_processed += summary.get("processed", 0)
                    total_failed += summary.get("failed", 0)
                    total_still_processing += summary.get("still_processing", 0)

                except Exception as e:
                    logger.error(
                        f"[poll_evaluation_batches] Error processing org_id={org.id}: {e}",
                        exc_info=True,
                    )
                    results.append(
                        {"org_id": org.id, "org_name": org.name, "error": str(e)}
                    )

            logger.info(
                f"[poll_evaluation_batches] Completed: "
                f"{total_processed} processed, {total_failed} failed, "
                f"{total_still_processing} still processing"
            )

            return {
                "status": "success",
                "organizations_processed": len(orgs),
                "total_processed": total_processed,
                "total_failed": total_failed,
                "total_still_processing": total_still_processing,
                "results": results,
            }

    except Exception as e:
        logger.error(
            f"[poll_evaluation_batches] Fatal error: {e}",
            exc_info=True,
        )
        # Retry the task after 5 minutes
        raise self.retry(exc=e, countdown=300, max_retries=3)
