import logging
from typing import List, Optional, Tuple
from sqlmodel import Session
from langfuse import Langfuse

from app.models import UserOrganization, ResponsesSyncAPIRequest, UserProjectOrg
from app.crud.credentials import get_provider_credential
from app.crud.assistants import get_assistant_by_id
from app.api.routes.responses import responses_sync
from app.core.util import configure_langfuse
from app.models.evaluation import Experiment, EvaluationResult

logger = logging.getLogger(__name__)


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
    # Get Langfuse credentials
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=project_id,
    )
    if not langfuse_credentials:
        return False, None, "Langfuse credentials not configured for this organization"

    # Configure Langfuse client
    langfuse, success = configure_langfuse(langfuse_credentials)
    if not success:
        return False, None, "Failed to configure Langfuse client"

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
    """
    Internal function to process the evaluation.

    This function iterates through dataset items, generates responses for each,
    and scores the results using Langfuse.
    """
    # Get assistant configuration
    assistant = get_assistant_by_id(
        session=_session, assistant_id=assistant_id, project_id=project_id
    )
    if not assistant:
        return False, None, f"Assistant {assistant_id} not found"

    # Get dataset from Langfuse
    logger.info(f"Fetching dataset: {dataset_name}")
    dataset = langfuse.get_dataset(dataset_name)

    results: List[EvaluationResult] = []
    total_items = len(dataset.items)
    logger.info(f"Processing {total_items} items from {dataset_name} dataset")

    # Create UserProjectOrg from UserOrganization for responses endpoint
    user_project_org = UserProjectOrg(
        user_id=_current_user.user_id,
        organization_id=_current_user.organization_id,
        project_id=project_id,
    )

    # Process each item in the dataset
    for idx, item in enumerate(dataset.items, 1):
        logger.info(
            f"Processing item {idx}/{total_items}: {item.input[:50] if len(item.input) > 50 else item.input}..."
        )

        # Create a trace for this evaluation
        with item.observe(run_name=experiment_name) as trace_id:
            # Prepare request for response generation
            request = ResponsesSyncAPIRequest(
                model=assistant.model,
                instructions=assistant.instructions,
                vector_store_ids=assistant.vector_store_ids,
                max_num_results=assistant.max_num_results,
                temperature=assistant.temperature,
                response_id=None,
                question=item.input,
            )

            # Generate response synchronously
            response = await responses_sync(
                request=request,
                _session=_session,
                _current_user=user_project_org,
            )

            # Extract message and response_id from response
            response_data = None
            if hasattr(response, "body"):
                # JSONResponse case
                import json

                response_data = json.loads(response.body.decode())
            elif isinstance(response, dict):
                # Direct dict response
                response_data = response

            if response_data and response_data.get("success"):
                output = response_data.get("data", {}).get("message", "")
                response_id = response_data.get("data", {}).get("response_id")
            else:
                output = ""
                response_id = None

            # Evaluate based on response success
            is_match = bool(output)

            # Score the result in Langfuse
            langfuse.score(
                trace_id=trace_id, name="response_generation_success", value=is_match
            )

            # Append result
            results.append(
                EvaluationResult(
                    input=item.input,
                    output=output,
                    expected=item.expected_output,
                    match=is_match,
                    response_id=response_id if is_match else None,
                )
            )
            logger.info(f"Completed item {idx} (success: {is_match})")

    # Flush Langfuse events to ensure all traces are sent
    langfuse.flush()

    # Calculate summary statistics
    matches = sum(1 for r in results if r.match)
    logger.info(f"Evaluation completed. Total: {len(results)}, Successful: {matches}")

    return (
        True,
        Experiment(
            experiment_name=experiment_name,
            dataset_name=dataset_name,
            results=results,
            total_items=len(results),
            matches=matches,
            note="All responses have been processed synchronously.",
        ),
        None,
    )
