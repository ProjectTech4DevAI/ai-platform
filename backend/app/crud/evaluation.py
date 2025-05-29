import logging
from typing import Dict, List, Optional, Tuple
from sqlmodel import Session
from langfuse import Langfuse

from app.models import UserOrganization
from app.crud.credentials import get_provider_credential
from app.api.routes.threads import threads_sync
from app.core.util import configure_langfuse, configure_openai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_evaluation(
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    project_id: int,
    _session: Session,
    _current_user: UserOrganization,
) -> Tuple[bool, Dict, Optional[str]]:
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
        Tuple of (success, response_data, error_message)
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
        return False, {}, "OpenAI API key not configured for this organization."

    # Get Langfuse credentials
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=project_id,
    )
    if not langfuse_credentials:
        return False, {}, "LANGFUSE keys not configured for this organization."

    # Configure Langfuse
    langfuse, success = configure_langfuse(langfuse_credentials)
    if not success:
        return False, {}, "Failed to configure Langfuse client."

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
        return False, {}, str(e)


async def _process_evaluation(
    langfuse: Langfuse,
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    project_id: int,
    _session: Session,
    _current_user: UserOrganization,
) -> Tuple[bool, Dict, Optional[str]]:
    """Internal function to process the evaluation."""
    # Get dataset
    logger.info(f"Fetching dataset: {dataset_name}")
    dataset = langfuse.get_dataset(dataset_name)
    results: List[Dict] = []
    total_items = len(dataset.items)
    logger.info(f"Processing {total_items} items from {dataset_name} dataset")

    for idx, item in enumerate(dataset.items, 1):
        logger.info(f"Processing item {idx}/{total_items}: {item.input[:20]}...")
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
                trace_id=trace_id, name="thread_creation_success", value=is_match
            )
            results.append(
                {
                    "input": item.input,
                    "output": output,
                    "expected": item.expected_output,
                    "match": is_match,
                    "thread_id": thread_id if is_match else None,
                }
            )
            logger.info(f"Completed processing item {idx} (match: {is_match})")

    # Flush Langfuse events
    langfuse.flush()

    matches = sum(1 for r in results if r["match"])
    logger.info(
        f"Evaluation completed. Total items: {len(results)}, Matches: {matches}"
    )

    return (
        True,
        {
            "experiment_name": experiment_name,
            "dataset_name": dataset_name,
            "results": results,
            "total_items": len(results),
            "matches": matches,
            "note": "All threads have been processed synchronously.",
        },
        None,
    )
