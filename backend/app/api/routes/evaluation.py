import logging
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_current_user_org, get_db
from app.models import UserOrganization
from app.utils import APIResponse
from app.crud.evaluation import run_evaluation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluation"])


@router.post("/evaluate")
async def evaluate_threads(
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    project_id: int,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """
    Endpoint to run Lanfuse evaluations using LLM-as-a-judge.
    Read more here: https://langfuse.com/changelog/2024-11-19-llm-as-a-judge-for-datasets
    """
    logger.info(
        f"Starting evaluation for experiment: {experiment_name}, dataset: {dataset_name}, assistant: {assistant_id}"
    )

    success, data, error = await run_evaluation(
        experiment_name=experiment_name,
        assistant_id=assistant_id,
        dataset_name=dataset_name,
        project_id=project_id,
        _session=_session,
        _current_user=_current_user,
    )

    if not success:
        return APIResponse.failure_response(error=error)

    return APIResponse.success_response(data=data)
