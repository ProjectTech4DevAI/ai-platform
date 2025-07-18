import re
import openai
import requests

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlmodel import Session
from typing import Optional
from langfuse.decorators import observe, langfuse_context

from app.api.deps import get_current_user_org, get_db, get_current_user_org_project
from app.core import logging, settings
from app.models import UserOrganization, OpenAIThreadCreate, UserProjectOrg
from app.crud import upsert_thread_result, get_thread_result
from app.utils import APIResponse
from app.crud.credentials import get_provider_credential
from app.core.util import configure_openai
from app.core.langfuse.langfuse import LangfuseTracer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["threads"])


class StartThreadRequest(BaseModel):
    question: str = Field(..., description="The user's input question.")
    assistant_id: str = Field(..., description="The ID of the assistant to be used.")
    remove_citation: bool = Field(
        default=False, description="Whether to remove citations from the response."
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="An optional existing thread ID to continue the conversation.",
    )


def send_callback(callback_url: str, data: dict):
    """Send results to the callback URL (synchronously)."""
    try:
        session = requests.Session()
        # uncomment this to run locally without SSL
        # session.verify = False
        response = session.post(callback_url, json=data)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Callback failed: {str(e)}", exc_info=True)
        return False


def handle_openai_error(e: openai.OpenAIError) -> str:
    """Extract error message from OpenAI error."""
    if isinstance(e.body, dict) and "message" in e.body:
        return e.body["message"]
    return str(e)


def validate_thread(client: OpenAI, thread_id: str) -> tuple[bool, str]:
    """Validate if a thread exists and has no active runs."""
    if not thread_id:
        return True, None

    try:
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        if runs.data and len(runs.data) > 0:
            latest_run = runs.data[0]
            if latest_run.status in ["queued", "in_progress", "requires_action"]:
                return (
                    False,
                    f"There is an active run on this thread (status: {latest_run.status}). Please wait for it to complete.",
                )
        return True, None
    except openai.OpenAIError:
        return False, f"Invalid thread ID provided {thread_id}"


def setup_thread(client: OpenAI, request: dict) -> tuple[bool, str]:
    """Set up thread and add message, either creating new or using existing."""
    thread_id = request.get("thread_id")
    if thread_id:
        try:
            client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=request["question"]
            )
            return True, None
        except openai.OpenAIError as e:
            return False, handle_openai_error(e)
    else:
        try:
            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id, role="user", content=request["question"]
            )
            request["thread_id"] = thread.id
            return True, None
        except openai.OpenAIError as e:
            return False, handle_openai_error(e)


def process_message_content(message_content: str, remove_citation: bool) -> str:
    """Process message content, optionally removing citations."""
    if remove_citation:
        return re.sub(r"【\d+(?::\d+)?†[^】]*】", "", message_content)
    return message_content


def get_additional_data(request: dict) -> dict:
    """Extract additional data from request, excluding specific keys."""
    return {
        k: v
        for k, v in request.items()
        if k not in {"question", "assistant_id", "callback_url", "thread_id"}
    }


def create_success_response(request: dict, message: str) -> APIResponse:
    """Create a success response with the given message and request data."""
    additional_data = get_additional_data(request)
    return APIResponse.success_response(
        data={
            "status": "success",
            "message": message,
            "thread_id": request["thread_id"],
            "endpoint": getattr(request, "endpoint", "some-default-endpoint"),
            **additional_data,
        }
    )


def run_and_poll_thread(client: OpenAI, thread_id: str, assistant_id: str):
    """Runs and polls a thread with the specified assistant using the OpenAI client."""
    return client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )


def extract_response_from_thread(
    client: OpenAI, thread_id: str, remove_citation: bool = False
) -> str:
    """Fetches and processes the latest message from a thread."""
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    latest_message = messages.data[0]
    message_content = latest_message.content[0].text.value
    return process_message_content(message_content, remove_citation)


def process_run_core(
    request: dict, client: OpenAI, tracer: LangfuseTracer
) -> tuple[dict, str]:
    """Core function to process a run and return the response and message with Langfuse tracing."""
    tracer.start_generation(
        name="openai_thread_run",
        input={"question": request["question"]},
        metadata={"assistant_id": request["assistant_id"]},
    )

    try:
        run = client.beta.threads.runs.create_and_poll(
            thread_id=request["thread_id"],
            assistant_id=request["assistant_id"],
        )

        if run.status == "completed":
            message = extract_response_from_thread(
                client, request["thread_id"], request.get("remove_citation", False)
            )
            tracer.end_generation(
                output={
                    "thread_id": request["thread_id"],
                    "message": message,
                },
                usage={
                    "input": run.usage.prompt_tokens,
                    "output": run.usage.completion_tokens,
                    "total": run.usage.total_tokens,
                    "unit": "TOKENS",
                },
                model=run.model,
            )
            tracer.update_trace(
                tags=[request["thread_id"]],
                output={"status": "success", "message": message, "error": None},
            )
            diagnostics = {
                "input_tokens": run.usage.prompt_tokens,
                "output_tokens": run.usage.completion_tokens,
                "total_tokens": run.usage.total_tokens,
                "model": run.model,
            }
            request = {**request, **{"diagnostics": diagnostics}}
            return create_success_response(request, message).model_dump(), None
        else:
            error_msg = f"Run failed with status: {run.status}"
            tracer.log_error(error_msg)
            return APIResponse.failure_response(error=error_msg).model_dump(), error_msg

    except openai.OpenAIError as e:
        error_msg = handle_openai_error(e)
        tracer.log_error(error_msg)
        return APIResponse.failure_response(error=error_msg).model_dump(), error_msg
    finally:
        tracer.flush()


def process_run(request: dict, client: OpenAI, tracer: LangfuseTracer):
    """Process a run and send callback with results with Langfuse tracing."""
    response, _ = process_run_core(request, client, tracer)
    send_callback(request["callback_url"], response)


def poll_run_and_prepare_response(request: dict, client: OpenAI, db: Session):
    """Handles a thread run, processes the response, and upserts the result to the database."""
    thread_id = request["thread_id"]
    prompt = request["question"]

    try:
        run = run_and_poll_thread(client, thread_id, request["assistant_id"])

        status = run.status or "unknown"
        response = None
        error = None

        if status == "completed":
            response = extract_response_from_thread(
                client, thread_id, request.get("remove_citation", False)
            )

    except openai.OpenAIError as e:
        status = "failed"
        error = str(e)
        response = None

    upsert_thread_result(
        db,
        OpenAIThreadCreate(
            thread_id=thread_id,
            prompt=prompt,
            response=response,
            status=status,
            error=error,
        ),
    )


@router.post("/threads")
async def threads(
    request: dict,
    background_tasks: BackgroundTasks,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Asynchronous endpoint that processes requests in background."""
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request.get("project_id"),
    )
    client, success = configure_openai(credentials)
    if not success:
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
        )

    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=request.get("project_id"),
    )

    # Validate thread
    is_valid, error_message = validate_thread(client, request.get("thread_id"))
    if not is_valid:
        raise Exception(error_message)
    # Setup thread
    is_success, error_message = setup_thread(client, request)
    if not is_success:
        raise Exception(error_message)

    # Send immediate response
    initial_response = APIResponse.success_response(
        data={
            "status": "processing",
            "message": "Run started",
            "thread_id": request.get("thread_id"),
            "success": True,
        }
    )

    tracer = LangfuseTracer(
        credentials=langfuse_credentials,
        session_id=request.get("thread_id"),
    )

    tracer.start_trace(
        name="threads_async_endpoint",
        input={
            "question": request["question"],
            "assistant_id": request["assistant_id"],
        },
        metadata={"thread_id": request["thread_id"]},
    )
    # Schedule background task
    background_tasks.add_task(process_run, request, client, tracer)

    return initial_response


@router.post("/threads/sync")
async def threads_sync(
    request: dict,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Synchronous endpoint that processes requests immediately."""
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request.get("project_id"),
    )

    # Configure OpenAI client
    client, success = configure_openai(credentials)
    if not success:
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
        )

    # Get Langfuse credentials
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=request.get("project_id"),
    )

    # Validate thread
    is_valid, error_message = validate_thread(client, request.get("thread_id"))
    if not is_valid:
        raise Exception(error_message)
    # Setup thread
    is_success, error_message = setup_thread(client, request)
    if not is_success:
        raise Exception(error_message)

    tracer = LangfuseTracer(
        credentials=langfuse_credentials,
        session_id=request.get("thread_id"),
    )

    tracer.start_trace(
        name="threads_sync_endpoint",
        input={
            "question": request.get("question"),
            "assistant_id": request.get("assistant_id"),
        },
        metadata={"thread_id": request.get("thread_id")},
    )

    try:
        response, error_message = process_run_core(request, client, tracer)
        return response
    finally:
        tracer.flush()


@router.post("/threads/start")
async def start_thread(
    request: StartThreadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Create a new OpenAI thread for the given question and start polling in the background.
    """
    request = request.model_dump()
    prompt = request["question"]
    credentials = get_provider_credential(
        session=db,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=_current_user.project_id,
    )

    # Configure OpenAI client
    client, success = configure_openai(credentials)
    if not success:
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
        )

    is_success, error = setup_thread(client, request)
    if not is_success:
        raise Exception(error)

    thread_id = request["thread_id"]

    upsert_thread_result(
        db,
        OpenAIThreadCreate(
            thread_id=thread_id,
            prompt=prompt,
            response=None,
            status="processing",
            error=None,
        ),
    )

    background_tasks.add_task(poll_run_and_prepare_response, request, client, db)

    return APIResponse.success_response(
        data={
            "thread_id": thread_id,
            "prompt": prompt,
            "status": "processing",
            "message": "Thread created and polling started in background.",
        }
    )


@router.get("/threads/result/{thread_id}")
async def get_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """
    Retrieve the result of a previously started OpenAI thread using its thread ID.
    """
    result = get_thread_result(db, thread_id)

    if not result:
        raise HTTPException(404, "thread not found")

    status = result.status or ("success" if result.response else "processing")

    return APIResponse.success_response(
        data={
            "thread_id": result.thread_id,
            "prompt": result.prompt,
            "status": status,
            "response": result.response,
            "error": result.error,
        }
    )
