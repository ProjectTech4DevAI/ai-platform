from fastapi import APIRouter, Depends
from sqlmodel import Session
from langfuse import Langfuse
from langfuse.decorators import langfuse_context

from app.api.deps import get_current_user_org, get_db
from app.models import UserOrganization
from app.utils import APIResponse
from app.crud.credentials import get_provider_credential
from app.api.routes.threads import threads_sync
from app.core.util import configure_langfuse

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
    """Endpoint to run thread evaluations using Langfuse."""
    # Get OpenAI credentials
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=project_id,
    )
    if not credentials or "api_key" not in credentials:
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
        )

    # Get Langfuse credentials
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=project_id,
    )
    if not langfuse_credentials:
        return APIResponse.failure_response(
            error="LANGFUSE keys not configured for this organization."
        )

    # Configure Langfuse
    langfuse, success = configure_langfuse(langfuse_credentials)
    if not success:
        return APIResponse.failure_response(
            error="Failed to configure Langfuse client."
        )

    try:
        # Get dataset
        dataset = langfuse.get_dataset(dataset_name)
        results = []

        for item in dataset.items:
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
                is_match = bool(output)  # Simplified evaluation for now
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

        # Flush Langfuse events
        langfuse_context.flush()
        langfuse.flush()

        return APIResponse.success_response(
            data={
                "experiment_name": experiment_name,
                "dataset_name": dataset_name,
                "results": results,
                "total_items": len(results),
                "matches": sum(1 for r in results if r["match"]),
                "note": "All threads have been processed synchronously.",
            }
        )

    except Exception as e:
        return APIResponse.failure_response(error=str(e))
