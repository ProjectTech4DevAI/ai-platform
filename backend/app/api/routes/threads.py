import re
import openai
import requests

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlmodel import Session
from typing import Optional
from langfuse.decorators import observe, langfuse_context

from app.api.deps import get_current_user_org, get_db
from app.core import logging, settings
from app.models import UserOrganization, OpenAIThreadCreate
from app.crud import upsert_thread_result, get_thread_result
from app.utils import APIResponse
from app.crud.credentials import get_provider_credential
from app.core.util import configure_langfuse, configure_openai

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
    logger.info(
        f"[send_callback] Starting callback request | {{'callback_url': '{callback_url}'}}"
    )
    try:
        session = requests.Session()
        # uncomment this to run locally without SSL
        # session.verify = False
        response = session.post(callback_url, json=data)
        response.raise_for_status()
        logger.info(
            f"[send_callback] Callback sent successfully | {{'callback_url': '{callback_url}', 'status_code': {response.status_code}}}"
        )
        return True
    except requests.RequestException as e:
        logger.error(
            f"[send_callback] Callback failed | {{'callback_url': '{callback_url}', 'error': '{str(e)}'}}"
        )
        return False


def handle_openai_error(e: openai.OpenAIError) -> str:
    """Extract error message from OpenAI error."""
    logger.info(
        f"[handle_openai_error] Processing OpenAI error | {{'error_type': '{type(e).__name__}'}}"
    )
    if isinstance(e.body, dict) and "message" in e.body:
        error_message = e.body["message"]
        logger.info(
            f"[handle_openai_error] Error message extracted | {{'error_message': '{error_message}'}}"
        )
        return error_message
    error_message = str(e)
    logger.info(
        f"[handle_openai_error] Fallback error message | {{'error_message': '{error_message}'}}"
    )
    return error_message


def validate_thread(client: OpenAI, thread_id: str) -> tuple[bool, str]:
    """Validate if a thread exists and has no active runs."""
    logger.info(
        f"[validate_thread] Starting thread validation | {{'thread_id': '{thread_id}'}}"
    )
    if not thread_id:
        logger.info(
            f"[validate_thread] No thread ID provided, validation skipped | {{}}"
        )
        return True, None

    try:
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        logger.info(
            f"[validate_thread] Retrieved runs for thread | {{'thread_id': '{thread_id}', 'run_count': {len(runs.data)}}}"
        )
        if runs.data and len(runs.data) > 0:
            latest_run = runs.data[0]
            if latest_run.status in ["queued", "in_progress", "requires_action"]:
                error_msg = f"There is an active run on this thread (status: {latest_run.status}). Please wait for it to complete."
                logger.warning(
                    f"[validate_thread] Active run detected | {{'thread_id': '{thread_id}', 'run_status': '{latest_run.status}'}}"
                )
                return False, error_msg
        logger.info(
            f"[validate_thread] Thread validated successfully | {{'thread_id': '{thread_id}'}}"
        )
        return True, None
    except openai.OpenAIError as e:
        error_msg = f"Invalid thread ID provided {thread_id}"
        logger.error(
            f"[validate_thread] Invalid thread ID | {{'thread_id': '{thread_id}', 'error': '{str(e)}'}}"
        )
        return False, error_msg


def setup_thread(client: OpenAI, request: dict) -> tuple[bool, str]:
    """Set up thread and add message, either creating new or using existing."""
    logger.info(
        f"[setup_thread] Starting thread setup | {{'thread_id': '{request.get('thread_id')}', 'assistant_id': '{request.get('assistant_id')}'}}"
    )
    thread_id = request.get("thread_id")
    if thread_id:
        try:
            client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=request["question"]
            )
            logger.info(
                f"[setup_thread] Message added to existing thread | {{'thread_id': '{thread_id}'}}"
            )
            return True, None
        except openai.OpenAIError as e:
            error_msg = handle_openai_error(e)
            logger.error(
                f"[setup_thread] Failed to add message to thread | {{'thread_id': '{thread_id}', 'error': '{error_msg}'}}"
            )
            return False, error_msg
    else:
        try:
            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id, role="user", content=request["question"]
            )
            request["thread_id"] = thread.id
            logger.info(
                f"[setup_thread] New thread created and message added | {{'thread_id': '{thread.id}'}}"
            )
            return True, None
        except openai.OpenAIError as e:
            error_msg = handle_openai_error(e)
            logger.error(
                f"[setup_thread] Failed to create new thread | {{'error': '{error_msg}'}}"
            )
            return False, error_msg


def process_message_content(message_content: str, remove_citation: bool) -> str:
    """Process message content, optionally removing citations."""
    logger.info(
        f"[process_message_content] Processing message content | {{'remove_citation': {remove_citation}}}"
    )
    if remove_citation:
        processed_content = re.sub(r"【\d+(?::\d+)?†[^】]*】", "", message_content)
        logger.info(
            f"[process_message_content] Citations removed | {{'content_length': {len(processed_content)}}}"
        )
        return processed_content
    logger.info(
        f"[process_message_content] No citations removed | {{'content_length': {len(message_content)}}}"
    )
    return message_content


def get_additional_data(request: dict) -> dict:
    """Extract additional data from request, excluding specific keys."""
    logger.info(
        f"[get_additional_data] Extracting additional data | {{'request_keys': {list(request.keys())}}}"
    )
    additional_data = {
        k: v
        for k, v in request.items()
        if k not in {"question", "assistant_id", "callback_url", "thread_id"}
    }
    logger.info(
        f"[get_additional_data] Additional data extracted | {{'additional_keys': {list(additional_data.keys())}}}"
    )
    return additional_data


def create_success_response(request: dict, message: str) -> APIResponse:
    """Create a success response with the given message and request data."""
    logger.info(
        f"[create_success_response] Creating success response | {{'thread_id': '{request.get('thread_id')}'}}"
    )
    additional_data = get_additional_data(request)
    response = APIResponse.success_response(
        data={
            "status": "success",
            "message": message,
            "thread_id": request["thread_id"],
            "endpoint": getattr(request, "endpoint", "some-default-endpoint"),
            **additional_data,
        }
    )
    logger.info(
        f"[create_success_response] Success response created | {{'thread_id': '{request.get('thread_id')}', 'status': 'success'}}"
    )
    return response


def run_and_poll_thread(client: OpenAI, thread_id: str, assistant_id: str):
    """Runs and polls a thread with the specified assistant using the OpenAI client."""
    logger.info(
        f"[run_and_poll_thread] Starting thread run and poll | {{'thread_id': '{thread_id}', 'assistant_id': '{assistant_id}'}}"
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    logger.info(
        f"[run_and_poll_thread] Thread run completed | {{'thread_id': '{thread_id}', 'status': '{run.status}'}}"
    )
    return run


def extract_response_from_thread(
    client: OpenAI, thread_id: str, remove_citation: bool = False
) -> str:
    """Fetches and processes the latest message from a thread."""
    logger.info(
        f"[extract_response_from_thread] Fetching thread response | {{'thread_id': '{thread_id}', 'remove_citation': {remove_citation}}}"
    )
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    latest_message = messages.data[0]
    message_content = latest_message.content[0].text.value
    processed_content = process_message_content(message_content, remove_citation)
    logger.info(
        f"[extract_response_from_thread] Response extracted | {{'thread_id': '{thread_id}', 'content_length': {len(processed_content)}}}"
    )
    return processed_content


@observe(as_type="generation")
def process_run_core(request: dict, client: OpenAI) -> tuple[dict, str]:
    """Core function to process a run and return the response and message."""
    logger.info(
        f"[process_run_core] Starting run processing | {{'thread_id': '{request.get('thread_id')}', 'assistant_id': '{request.get('assistant_id')}'}}"
    )
    try:
        run = client.beta.threads.runs.create_and_poll(
            thread_id=request["thread_id"],
            assistant_id=request["assistant_id"],
        )
        langfuse_context.update_current_trace(
            session_id=request["thread_id"],
            input=request["question"],
            name="Thread Run Started",
        )
        logger.info(
            f"[process_run_core] Thread run started | {{'thread_id': '{request.get('thread_id')}', 'run_status': '{run.status}'}}"
        )

        if run.status == "completed":
            langfuse_context.update_current_observation(
                model=run.model,
                usage_details={
                    "prompt_tokens": run.usage.prompt_tokens,
                    "completion_tokens": run.usage.completion_tokens,
                    "total_tokens": run.usage.total_tokens,
                },
            )
            messages = client.beta.threads.messages.list(thread_id=request["thread_id"])
            latest_message = messages.data[0]
            message_content = latest_message.content[0].text.value
            message = process_message_content(
                message_content, request.get("remove_citation", False)
            )
            langfuse_context.update_current_trace(
                output=message, name="Thread Run Completed"
            )
            diagnostics = {
                "input_tokens": run.usage.prompt_tokens,
                "output_tokens": run.usage.completion_tokens,
                "total_tokens": run.usage.total_tokens,
                "model": run.model,
            }
            request = {**request, **{"diagnostics": diagnostics}}
            logger.info(
                f"[process_run_core] Run completed successfully | {{'thread_id': '{request.get('thread_id')}', 'model': '{run.model}', 'total_tokens': {run.usage.total_tokens}}}"
            )

            return create_success_response(request, message).model_dump(), None
        else:
            error_msg = f"Run failed with status: {run.status}"
            logger.error(
                f"[process_run_core] Run failed | {{'thread_id': '{request.get('thread_id')}', 'status': '{run.status}', 'error': '{error_msg}'}}"
            )
            return APIResponse.failure_response(error=error_msg).model_dump(), error_msg

    except openai.OpenAIError as e:
        error_msg = handle_openai_error(e)
        logger.error(
            f"[process_run_core] OpenAI error during run | {{'thread_id': '{request.get('thread_id')}', 'error': '{error_msg}'}}"
        )
        return APIResponse.failure_response(error=error_msg).model_dump(), error_msg


@observe(as_type="generation")
def process_run(request: dict, client: OpenAI):
    """Process a run and send callback with results."""
    logger.info(
        f"[process_run] Starting background run processing | {{'thread_id': '{request.get('thread_id')}', 'callback_url': '{request.get('callback_url')}'}}"
    )
    response, _ = process_run_core(request, client)
    logger.info(
        f"[process_run] Sending callback with results | {{'thread_id': '{request.get('thread_id')}'}}"
    )
    send_callback(request["callback_url"], response)
    logger.info(
        f"[process_run] Background run processing completed | {{'thread_id': '{request.get('thread_id')}'}}"
    )


def poll_run_and_prepare_response(request: dict, client: OpenAI, db: Session):
    """Handles a thread run, processes the response, and upserts the result to the database."""
    thread_id = request["thread_id"]
    prompt = request["question"]
    logger.info(
        f"[poll_run_and_prepare_response] Starting thread polling | {{'thread_id': '{thread_id}', 'assistant_id': '{request.get('assistant_id')}'}}"
    )
    try:
        run = run_and_poll_thread(client, thread_id, request["assistant_id"])

        status = run.status or "unknown"
        response = None
        error = None
        logger.info(
            f"[poll_run_and_prepare_response] Run polled | {{'thread_id': '{thread_id}', 'status': '{status}'}}"
        )

        if status == "completed":
            response = extract_response_from_thread(
                client, thread_id, request.get("remove_citation", False)
            )
            logger.info(
                f"[poll_run_and_prepare_response] Response extracted | {{'thread_id': '{thread_id}', 'response_length': {len(response)}}}"
            )

    except openai.OpenAIError as e:
        status = "failed"
        error = str(e)
        response = None
        logger.error(
            f"[poll_run_and_prepare_response] OpenAI error during polling | {{'thread_id': '{thread_id}', 'error': '{str(e)}'}}"
        )

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
    logger.info(
        f"[poll_run_and_prepare_response] Thread result upserted | {{'thread_id': '{thread_id}', 'status': '{status}'}}"
    )


@router.post("/threads")
async def threads(
    request: dict,
    background_tasks: BackgroundTasks,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Asynchronous endpoint that processes requests in background."""
    logger.info(
        f"[threads] Starting async thread request | {{'org_id': {_current_user.organization_id}, 'user_id': {_current_user.user_id}, 'thread_id': '{request.get('thread_id')}'}}"
    )
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request.get("project_id"),
    )
    client, success = configure_openai(credentials)
    if not success:
        logger.warning(
            f"[threads] OpenAI credentials not configured | {{'org_id': {_current_user.organization_id}}}"
        )
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
        )
    logger.info(
        f"[threads] OpenAI client configured | {{'org_id': {_current_user.organization_id}}}"
    )

    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=request.get("project_id"),
    )
    if not langfuse_credentials:
        logger.warning(
            f"[threads] Langfuse credentials not configured | {{'org_id': {_current_user.organization_id}}}"
        )
        raise HTTPException(404, "LANGFUSE keys not configured for this organization.")
    logger.info(
        f"[threads] Langfuse credentials retrieved | {{'org_id': {_current_user.organization_id}}}"
    )

    # Configure Langfuse
    _, success = configure_langfuse(langfuse_credentials)
    if not success:
        logger.error(
            f"[threads] Failed to configure Langfuse client | {{'org_id': {_current_user.organization_id}}}"
        )
        return APIResponse.failure_response(
            error="Failed to configure Langfuse client."
        )
    logger.info(
        f"[threads] Langfuse client configured | {{'org_id': {_current_user.organization_id}}}"
    )

    # Validate thread
    is_valid, error_message = validate_thread(client, request.get("thread_id"))
    if not is_valid:
        logger.error(
            f"[threads] Thread validation failed | {{'thread_id': '{request.get('thread_id')}', 'error': '{error_message}'}}"
        )
        raise Exception(error_message)
    logger.info(
        f"[threads] Thread validated | {{'thread_id': '{request.get('thread_id')}'}}"
    )
    # Setup thread
    is_success, error_message = setup_thread(client, request)
    if not is_success:
        logger.error(
            f"[threads] Thread setup failed | {{'thread_id': '{request.get('thread_id')}', 'error': '{error_message}'}}"
        )
        raise Exception(error_message)
    logger.info(
        f"[threads] Thread setup completed | {{'thread_id': '{request.get('thread_id')}'}}"
    )

    # Send immediate response
    initial_response = APIResponse.success_response(
        data={
            "status": "processing",
            "message": "Run started",
            "thread_id": request.get("thread_id"),
            "success": True,
        }
    )
    logger.info(
        f"[threads] Sending initial response | {{'thread_id': '{request.get('thread_id')}', 'status': 'processing'}}"
    )

    # Schedule background task
    background_tasks.add_task(process_run, request, client)
    logger.info(
        f"[threads] Background task scheduled | {{'thread_id': '{request.get('thread_id')}'}}"
    )

    return initial_response


@router.post("/threads/sync")
async def threads_sync(
    request: dict,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Synchronous endpoint that processes requests immediately."""
    logger.info(
        f"[threads_sync] Starting sync thread request | {{'org_id': {_current_user.organization_id}, 'user_id': {_current_user.user_id}, 'thread_id': '{request.get('thread_id')}'}}"
    )
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request.get("project_id"),
    )

    # Configure OpenAI client
    client, success = configure_openai(credentials)
    if not success:
        logger.warning(
            f"[threads_sync] OpenAI credentials not configured | {{'org_id': {_current_user.organization_id}}}"
        )
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
        )
    logger.info(
        f"[threads_sync] OpenAI client configured | {{'org_id': {_current_user.organization_id}}}"
    )

    # Get Langfuse credentials
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=request.get("project_id"),
    )
    if not langfuse_credentials:
        logger.warning(
            f"[threads_sync] Langfuse credentials not configured | {{'org_id': {_current_user.organization_id}}}"
        )
        return APIResponse.failure_response(
            error="LANGFUSE keys not configured for this organization."
        )
    logger.info(
        f"[threads_sync] Langfuse credentials retrieved | {{'org_id': {_current_user.organization_id}}}"
    )

    # Configure Langfuse
    _, success = configure_langfuse(langfuse_credentials)
    if not success:
        logger.error(
            f"[threads_sync] Failed to configure Langfuse client | {{'org_id': {_current_user.organization_id}}}"
        )
        return APIResponse.failure_response(
            error="Failed to configure Langfuse client."
        )
    logger.info(
        f"[threads_sync] Langfuse client configured | {{'org_id': {_current_user.organization_id}}}"
    )

    # Validate thread
    is_valid, error_message = validate_thread(client, request.get("thread_id"))
    if not is_valid:
        logger.error(
            f"[threads_sync] Thread validation failed | {{'thread_id': '{request.get('thread_id')}', 'error': '{error_message}'}}"
        )
        raise Exception(error_message)
    logger.info(
        f"[threads_sync] Thread validated | {{'thread_id': '{request.get('thread_id')}'}}"
    )
    # Setup thread
    is_success, error_message = setup_thread(client, request)
    if not is_success:
        logger.error(
            f"[threads_sync] Thread setup failed | {{'thread_id': '{request.get('thread_id')}', 'error': '{error_message}'}}"
        )
        raise Exception(error_message)
    logger.info(
        f"[threads_sync] Thread setup completed | {{'thread_id': '{request.get('thread_id')}'}}"
    )

    try:
        response, error_message = process_run_core(request, client)
        logger.info(
            f"[threads_sync] Run processed successfully | {{'thread_id': '{request.get('thread_id')}'}}"
        )
        return response
    finally:
        langfuse_context.flush()
        logger.info(
            f"[threads_sync] Langfuse context flushed | {{'thread_id': '{request.get('thread_id')}'}}"
        )


@router.post("/threads/start")
async def start_thread(
    request: StartThreadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """
    Create a new OpenAI thread for the given question and start polling in the background.
    """
    logger.info(
        f"[start_thread] Starting thread creation | {{'org_id': {_current_user.organization_id}, 'user_id': {_current_user.user_id}, 'thread_id': '{request.thread_id}'}}"
    )
    request_dict = request.model_dump()
    prompt = request_dict["question"]
    credentials = get_provider_credential(
        session=db,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request_dict.get("project_id"),
    )

    # Configure OpenAI client
    client, success = configure_openai(credentials)
    if not success:
        logger.warning(
            f"[start_thread] OpenAI credentials not configured | {{'org_id': {_current_user.organization_id}}}"
        )
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
        )
    logger.info(
        f"[start_thread] OpenAI client configured | {{'org_id': {_current_user.organization_id}}}"
    )

    is_success, error = setup_thread(client, request_dict)
    if not is_success:
        logger.error(
            f"[start_thread] Thread setup failed | {{'thread_id': '{request_dict.get('thread_id')}', 'error': '{error}'}}"
        )
        raise Exception(error)
    logger.info(
        f"[start_thread] Thread setup completed | {{'thread_id': '{request_dict.get('thread_id')}'}}"
    )

    thread_id = request_dict["thread_id"]

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
    logger.info(
        f"[start_thread] Thread result upserted | {{'thread_id': '{thread_id}', 'status': 'processing'}}"
    )

    background_tasks.add_task(poll_run_and_prepare_response, request_dict, client, db)
    logger.info(
        f"[start_thread] Background polling task scheduled | {{'thread_id': '{thread_id}'}}"
    )

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
    logger.info(
        f"[get_thread] Retrieving thread result | {{'thread_id': '{thread_id}', 'org_id': {_current_user.organization_id}, 'user_id': {_current_user.user_id}}}"
    )
    result = get_thread_result(db, thread_id)

    if not result:
        logger.warning(
            f"[get_thread] Thread not found | {{'thread_id': '{thread_id}', 'org_id': {_current_user.organization_id}}}"
        )
        raise HTTPException(404, "thread not found")

    status = result.status or ("success" if result.response else "processing")
    logger.info(
        f"[get_thread] Thread result retrieved | {{'thread_id': '{thread_id}', 'status': '{status}'}}"
    )

    return APIResponse.success_response(
        data={
            "thread_id": result.thread_id,
            "prompt": result.prompt,
            "status": status,
            "response": result.response,
            "error": result.error,
        }
    )
