import logging
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_current_user_org, get_db
from app.models import UserOrganization
from app.crud.evaluation import run_evaluation
from app.models.evaluation import Experiment

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluation"])


@router.post("/evaluate", response_model=Experiment)
async def evaluate_responses(
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    project_id: int,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
) -> Experiment:
    """
    Endpoint to run Langfuse evaluations using LLM-as-a-judge.

    This endpoint processes a dataset from Langfuse, generates responses for each item
    using the specified assistant, and evaluates the results.

    Read more: https://langfuse.com/changelog/2024-11-19-llm-as-a-judge-for-datasets

    Args:
        experiment_name: Name of the experiment run
        assistant_id: ID of the assistant to use for generating responses
        dataset_name: Name of the Langfuse dataset to evaluate against
        project_id: Project ID for credential lookup
        _session: Database session (injected)
        _current_user: Current user organization (injected)

    Returns:
        Experiment object containing evaluation results and statistics
    """
    logger.info(
        f"Starting evaluation - experiment: {experiment_name}, "
        f"dataset: {dataset_name}, assistant: {assistant_id}"
    )

    success, data, error = await run_evaluation(
        experiment_name=experiment_name,
        assistant_id=assistant_id,
        dataset_name=dataset_name,
        project_id=project_id,
        _session=_session,
        _current_user=_current_user,
    )

    if not success or data is None:
        raise ValueError(error or "Failed to run evaluation")

    return data
