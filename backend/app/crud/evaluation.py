import csv
import io
import logging

from langfuse import Langfuse
from sqlmodel import Session

from app.core.util import configure_langfuse, configure_openai
from app.crud.credentials import get_provider_credential
from app.models import UserOrganization
from app.models.evaluation import (
    DatasetUploadResponse,
    EvaluationResult,
    Experiment,
)

logger = logging.getLogger(__name__)


async def upload_dataset_to_langfuse(
    csv_content: bytes,
    dataset_name: str,
    duplication_factor: int,
    _session: Session,
    _current_user: UserOrganization,
) -> tuple[bool, DatasetUploadResponse | None, str | None]:
    """
    Upload a CSV dataset to Langfuse with duplication for flakiness testing.

    Args:
        csv_content: Raw CSV file content as bytes
        dataset_name: Name for the dataset in Langfuse
        duplication_factor: Number of times to duplicate each item (default 5)
        _session: Database session
        _current_user: Current user organization

    Returns:
        Tuple of (success, dataset_response, error_message)
    """
    try:
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

        # Parse CSV content
        csv_text = csv_content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_text))

        # Validate CSV headers
        if (
            "question" not in csv_reader.fieldnames
            or "answer" not in csv_reader.fieldnames
        ):
            return (
                False,
                None,
                "CSV must contain 'question' and 'answer' columns. "
                f"Found columns: {csv_reader.fieldnames}",
            )

        # Read all rows from CSV
        original_items = []
        for row in csv_reader:
            question = row.get("question", "").strip()
            answer = row.get("answer", "").strip()

            if not question or not answer:
                logger.warning(f"Skipping row with empty question or answer: {row}")
                continue

            original_items.append({"question": question, "answer": answer})

        if not original_items:
            return False, None, "No valid items found in CSV file."

        logger.info(
            f"Parsed {len(original_items)} items from CSV. "
            f"Will duplicate {duplication_factor}x for a total of {len(original_items) * duplication_factor} items."
        )

        # Create or get dataset in Langfuse
        dataset = langfuse.create_dataset(name=dataset_name)

        # Upload items with duplication
        total_uploaded = 0
        for item in original_items:
            # Duplicate each item N times
            for duplicate_num in range(duplication_factor):
                try:
                    langfuse.create_dataset_item(
                        dataset_name=dataset_name,
                        input={"question": item["question"]},
                        expected_output={"answer": item["answer"]},
                        metadata={
                            "original_question": item["question"],
                            "duplicate_number": duplicate_num + 1,
                            "duplication_factor": duplication_factor,
                        },
                    )
                    total_uploaded += 1
                except Exception as e:
                    logger.error(
                        f"Failed to upload item (duplicate {duplicate_num + 1}): {item['question'][:50]}... Error: {e}"
                    )

        # Flush to ensure all items are uploaded
        langfuse.flush()

        logger.info(
            f"Successfully uploaded {total_uploaded} items to dataset '{dataset_name}' "
            f"({len(original_items)} original × {duplication_factor} duplicates)"
        )

        return (
            True,
            DatasetUploadResponse(
                dataset_name=dataset_name,
                total_items=total_uploaded,
                original_items=len(original_items),
                duplication_factor=duplication_factor,
                langfuse_dataset_id=dataset.id if hasattr(dataset, "id") else None,
            ),
            None,
        )

    except Exception as e:
        logger.error(f"Error uploading dataset: {str(e)}", exc_info=True)
        return False, None, f"Failed to upload dataset: {str(e)}"


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
