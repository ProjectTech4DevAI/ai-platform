import re
import openai
import requests

from fastapi import APIRouter, BackgroundTasks, Depends
from openai import OpenAI
from sqlmodel import Session
from langfuse.decorators import observe, langfuse_context

from app.api.deps import get_current_user_org, get_db
from app.core import logging, settings
from app.models import UserOrganization
from app.utils import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["threads"])


def send_callback(callback_url: str, data: dict):
    """Send results to the callback URL (synchronously)."""
    try:
        session = requests.Session()
        # uncomment this to run locally without SSL
        session.verify = False
        response = session.post(callback_url, json=data)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Callback failed: {str(e)}")
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


@observe(as_type="generation")
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
            langfuse_context.update_current_trace(
                session_id=thread.id, name="Setting up new Thread", output=thread.id
            )
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


@observe(as_type="generation")
def process_run(request: dict, client: OpenAI):
    """Process a run and send callback with results."""
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

            callback_response = create_success_response(request, message)
        else:
            callback_response = APIResponse.failure_response(
                error=f"Run failed with status: {run.status}"
            )

        send_callback(request["callback_url"], callback_response.model_dump())

    except openai.OpenAIError as e:
        callback_response = APIResponse.failure_response(error=handle_openai_error(e))
        send_callback(request["callback_url"], callback_response.model_dump())


@router.post("/threads")
async def threads(
    request: dict,
    background_tasks: BackgroundTasks,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Asynchronous endpoint that processes requests in background."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    langfuse_context.configure(
        secret_key=settings.LANGFUSE_SECRET_KEY,
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        host=settings.LANGFUSE_HOST,
    )
    # Validate thread
    is_valid, error_message = validate_thread(client, request.get("thread_id"))
    if not is_valid:
        return APIResponse.failure_response(error=error_message)

    # Setup thread
    is_success, error_message = setup_thread(client, request)
    if not is_success:
        return APIResponse.failure_response(error=error_message)

    # Send immediate response
    initial_response = APIResponse.success_response(
        data={
            "status": "processing",
            "message": "Run started",
            "thread_id": request.get("thread_id"),
            "success": True,
        }
    )

    # Schedule background task
    background_tasks.add_task(process_run, request, client)

    return initial_response


@router.post("/threads/sync")
async def threads_sync(
    request: dict,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Synchronous endpoint that processes requests immediately."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Validate thread
    is_valid, error_message = validate_thread(client, request.get("thread_id"))
    if not is_valid:
        return APIResponse.failure_response(error=error_message)

    # Setup thread
    is_success, error_message = setup_thread(client, request)
    if not is_success:
        return APIResponse.failure_response(error=error_message)

    try:
        # Process run
        run = client.beta.threads.runs.create_and_poll(
            thread_id=request["thread_id"],
            assistant_id=request["assistant_id"],
        )

        if run.status == "completed":
            messages = client.beta.threads.messages.list(thread_id=request["thread_id"])
            latest_message = messages.data[0]
            message_content = latest_message.content[0].text.value
            message = process_message_content(
                message_content, request.get("remove_citation", False)
            )
            return create_success_response(request, message)
        else:
            return APIResponse.failure_response(
                error=f"Run failed with status: {run.status}"
            )

    except openai.OpenAIError as e:
        return APIResponse.failure_response(error=handle_openai_error(e))
