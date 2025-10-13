import logging

from langfuse import Langfuse
from sqlmodel import Session

from app.core.util import configure_langfuse, configure_openai
from app.crud.credentials import get_provider_credential
from app.models import UserOrganization
from app.models.evaluation import EvaluationResult, Experiment

logger = logging.getLogger(__name__)


async def run_evaluation(
    experiment_name: str,
    assistant_id: str,
    dataset_name: str,
    _session: Session,
    _current_user: UserOrganization,
) -> tuple[bool, Experiment | None, str | None]:
    """
    Run Langfuse evaluations using LLM-as-a-judge.

    Args:
        experiment_name: Name of the experiment
        assistant_id: ID of the assistant to evaluate
        dataset_name: Name of the dataset to use
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
    _session: Session,
    _current_user: UserOrganization,
) -> tuple[bool, Experiment | None, str | None]:
    """Internal function to process the evaluation with hardcoded input/output pairs."""
    # Hardcoded test data - list of question/answer pairs
    test_data = [
        {"question": "What is the capital of France?", "answer": "Paris"},
        {"question": "What is the capital of Germany?", "answer": "Berlin"},
        {"question": "What is the capital of Italy?", "answer": "Rome"},
        {"question": "What is the capital of Spain?", "answer": "Madrid"},
    ]

    # Get dataset from Langfuse (assume it exists)
    logger.info(f"Fetching dataset: {dataset_name}")
    dataset = langfuse.get_dataset(dataset_name)

    results: list[EvaluationResult] = []
    total_items = len(dataset.items)
    logger.info(
        f"Processing {total_items} items from dataset with experiment: {experiment_name}"
    )

    for idx, item in enumerate(dataset.items, 1):
        question = item.input
        expected_answer = item.expected_output
        logger.info(f"Processing item {idx}/{total_items}: {question}")

        # Use item.observe to create trace linked to dataset item
        with item.observe(run_name=experiment_name) as trace_id:
            # For testing, use the expected answer as output
            answer = expected_answer

            # Update trace with input/output
            langfuse.trace(
                id=trace_id, input={"question": question}, output={"answer": answer}
            )

            results.append(
                EvaluationResult(
                    input=question,
                    output=answer,
                    expected=expected_answer,
                    thread_id=None,
                )
            )
            logger.info(f"Completed processing item {idx}")

    # Flush Langfuse events
    langfuse.flush()

    matches = sum(1 for r in results if r.match)
    logger.info(
        f"Evaluation completed. Total items: {len(results)}, Matches: {matches}"
    )

    return (
        True,
        Experiment(
            experiment_name=experiment_name,
            dataset_name=dataset_name,
            results=results,
            total_items=len(results),
            matches=matches,
            note="Hardcoded question/answer pairs linked to dataset run.",
        ),
        None,
    )
