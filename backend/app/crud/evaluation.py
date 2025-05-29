import logging
from typing import Dict, List, Optional, Tuple
from sqlmodel import Session
from langfuse import Langfuse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.models import UserOrganization
from app.crud.credentials import get_provider_credential
from app.api.routes.threads import threads_sync
from app.core.util import configure_langfuse, configure_openai
from app.models.evaluation import Experiment, EvaluationResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum number of concurrent tasks
MAX_CONCURRENT_TASKS = 5


async def run_evaluation(
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    project_id: int,
    _session: Session,
    _current_user: UserOrganization,
) -> Tuple[bool, Optional[Experiment], Optional[str]]:
    """
    Run Langfuse evaluations using LLM-as-a-judge.

    Args:
        experiment_name: Name of the experiment
        assistant_id: ID of the assistant to evaluate
        dataset_name: Name of the dataset to use
        project_id: Project ID
        _session: Database session
        _current_user: Current user organization

    Returns:
        Tuple of (success, experiment_data, error_message)
    """
    # Get OpenAI credentials
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=project_id,
    )

    # Configure OpenAI client
    client, success = configure_openai(credentials)
    if not success:
        return False, None, "OpenAI API key not configured for this organization."

    # Get Langfuse credentials
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=project_id,
    )
    if not langfuse_credentials:
        return False, None, "LANGFUSE keys not configured for this organization."

    # Configure Langfuse
    langfuse, success = configure_langfuse(langfuse_credentials)
    if not success:
        return False, None, "Failed to configure Langfuse client."

    try:
        return await _process_evaluation(
            langfuse=langfuse,
            experiment_name=experiment_name,
            assistant_id=assistant_id,
            dataset_name=dataset_name,
            project_id=project_id,
            _session=_session,
            _current_user=_current_user,
        )
    except Exception as e:
        logger.error(f"Error during evaluation: {str(e)}", exc_info=True)
        return False, None, str(e)


async def _process_evaluation(
    langfuse: Langfuse,
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    project_id: int,
    _session: Session,
    _current_user: UserOrganization,
) -> Tuple[bool, Optional[Experiment], Optional[str]]:
    """Internal function to process the evaluation."""
    # Get dataset
    logger.info(f"Fetching dataset: {dataset_name}")
    dataset = langfuse.get_dataset(dataset_name)
    total_items = len(dataset.items)
    logger.info(f"Processing {total_items} items from {dataset_name} dataset")

    # Create a semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    active_tasks = set()
    results = []

    async def process_item(idx: int, item) -> EvaluationResult:
        async with semaphore:
            start_time = datetime.now()
            task_id = id(asyncio.current_task())
            active_tasks.add(task_id)
            logger.info(
                f"[{start_time.strftime('%H:%M:%S')}] Starting item {idx}/{total_items} "
                f"(Task {task_id}, Active tasks: {len(active_tasks)}): {item.input[:20]}..."
            )

            try:
                with item.observe(run_name=experiment_name) as trace_id:
                    # Prepare request
                    request = {
                        "question": item.input,
                        "assistant_id": assistant_id,
                        "remove_citation": True,
                        "project_id": project_id,
                    }

                    # Process thread synchronously
                    response = await threads_sync(
                        request=request,
                        _session=_session,
                        _current_user=_current_user,
                    )

                    # Extract message from the response
                    if isinstance(response, dict) and response.get("success"):
                        output = response.get("data", {}).get("message", "")
                        thread_id = response.get("data", {}).get("thread_id")
                    else:
                        output = ""
                        thread_id = None

                    # Evaluate based on response success
                    is_match = bool(output)
                    langfuse.score(
                        trace_id=trace_id,
                        name="thread_creation_success",
                        value=is_match,
                    )

                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    logger.info(
                        f"[{end_time.strftime('%H:%M:%S')}] Completed item {idx}/{total_items} "
                        f"(Task {task_id}, Active tasks: {len(active_tasks)}, "
                        f"match: {is_match}, duration: {duration:.2f}s)"
                    )

                    return EvaluationResult(
                        input=item.input,
                        output=output,
                        expected=item.expected_output,
                        match=is_match,
                        thread_id=thread_id if is_match else None,
                    )
            finally:
                active_tasks.remove(task_id)

    # Create tasks for all items
    logger.info(
        f"Starting parallel processing of {total_items} items with max {MAX_CONCURRENT_TASKS} concurrent tasks"
    )

    # Create tasks and gather results
    tasks = []
    for idx, item in enumerate(dataset.items, 1):
        task = asyncio.create_task(process_item(idx, item))
        tasks.append(task)

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)

    # Flush Langfuse events
    langfuse.flush()

    matches = sum(1 for r in results if r.match)
    logger.info(
        f"Evaluation completed. Total items: {len(results)}, Matches: {matches}, "
        f"Success rate: {(matches/len(results))*100:.1f}%"
    )

    return (
        True,
        Experiment(
            experiment_name=experiment_name,
            dataset_name=dataset_name,
            results=results,
            total_items=len(results),
            matches=matches,
            note="All threads have been processed in parallel with semaphore control.",
        ),
        None,
    )
