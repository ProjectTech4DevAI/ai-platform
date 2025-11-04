import logging

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_current_active_superuser, get_db
from app.crud.evaluations import process_all_pending_evaluations_sync

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cron"])


@router.get(
    "/cron/evaluations",
    include_in_schema=True,
    dependencies=[Depends(get_current_active_superuser)],
)
def evaluation_cron_job(
    session: Session = Depends(get_db),
) -> dict:
    """
    Cron job endpoint for periodic evaluation tasks.

    This endpoint:
    1. Gets all organizations
    2. For each org, polls their pending evaluations
    3. Processes completed batches automatically
    4. Returns aggregated results

    Hidden from Swagger documentation.
    Requires authentication via FIRST_SUPERUSER credentials.
    """
    logger.info("[evaluation_cron_job] Cron job invoked")

    try:
        # Process all pending evaluations across all organizations
        result = process_all_pending_evaluations_sync(session=session)

        logger.info(
            f"[evaluation_cron_job] Completed: "
            f"orgs={result.get('organizations_processed', 0)}, "
            f"processed={result.get('total_processed', 0)}, "
            f"failed={result.get('total_failed', 0)}, "
            f"still_processing={result.get('total_still_processing', 0)}"
        )

        return result

    except Exception as e:
        logger.error(
            f"[evaluation_cron_job] Error executing cron job: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error": str(e),
            "organizations_processed": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_still_processing": 0,
        }
