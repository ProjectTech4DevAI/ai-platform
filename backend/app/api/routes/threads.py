import requests
import openai
from openai import OpenAI
from fastapi import APIRouter, BackgroundTasks
from app.models import ( MessageRequest, AckPayload, CallbackPayload)
from ...core.config import settings
from ...core.logger import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/threads", tags=["threads"])


def send_callback(callback_url: str, data: dict):
    """Send results to the callback URL (synchronously)."""
    try:
        print("completed")
        session = requests.Session()
        session.verify = False
        print(data)
        response = session.post(callback_url, json=data)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Callback failed: {str(e)}")
        return False


def build_callback_payload(request: MessageRequest, status: str, message: str) -> CallbackPayload:
    """
    Helper function to build the CallbackPayload from a MessageRequest.
    """
    data = {
        "status": status,
        "message": message,
        "thread_id": request.thread_id,
        "endpoint": getattr(request, "endpoint", "some-default-endpoint"),
    }

    # Update with any additional fields from request that we haven't excluded
    data.update(
        request.model_dump(exclude={"question", "assistant_id", "callback_url", "thread_id"})
    )

    return CallbackPayload(**data)


def process_run(request: MessageRequest, client: OpenAI):
    """
    Background task to run create_and_poll, then send the callback with the result.
    This function is run in the background after we have already returned an initial response.
    """
    try:
        print("Thread run started")
        # Start the run
        run = client.beta.threads.runs.create_and_poll(
            thread_id=request.thread_id,
            assistant_id=request.assistant_id,
        )

        if run.status == "completed":
            print("Thread run completed")
            messages = client.beta.threads.messages.list(thread_id=request.thread_id)
            latest_message = messages.data[0]
            message_content = latest_message.content[0].text.value

            callback_response = build_callback_payload(
                request=request, status="success", message=message_content
            )
        else:
            callback_response = build_callback_payload(
                request=request, status="error", message=f"Run failed with status: {run.status}"
            )

        # Send callback with results
        send_callback(request.callback_url, callback_response.model_dump())

    except openai.OpenAIError as e:
        # Handle any other OpenAI API errors
        if isinstance(e.body, dict) and "message" in e.body:
            error_message = e.body["message"]
        else:
            error_message = str(e)

        callback_response = build_callback_payload(
            request=request, status="error", message=error_message
        )

        send_callback(request.callback_url, callback_response.model_dump())


def validate_assistant_id(assistant_id: str, client: OpenAI):
    try:
        client.beta.assistants.retrieve(assistant_id=assistant_id)
    except openai.NotFoundError:
        return AckPayload(
            status="error",
            message=f"Invalid assistant ID provided {assistant_id}",
            success=False,
        )
    return None


@router.post("/")
async def threads(request: MessageRequest, background_tasks: BackgroundTasks):
    """
    Accepts a question, assistant_id, callback_url, and optional thread_id from the request body.
    Returns an immediate "processing" response, then continues to run create_and_poll in background.
    Once completed, calls send_callback with the final result.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    assistant_error = validate_assistant_id(request.assistant_id, client)
    if assistant_error:
        return assistant_error

    # 1. Validate or check if there's an existing thread with an in-progress run
    if request.thread_id:
        try:
            runs = client.beta.threads.runs.list(thread_id=request.thread_id)
            # Get the most recent run (first in the list) if any
            if runs.data and len(runs.data) > 0:
                latest_run = runs.data[0]
                if latest_run.status in ["queued", "in_progress", "requires_action"]:
                    return {
                        "status": "error",
                        "message": f"There is an active run on this thread (status: {latest_run.status}). Please wait for it to complete.",
                    }
        except openai.NotFoundError:
            # Handle invalid thread ID
            return AckPayload(
                status="error",
                message=f"Invalid thread ID provided {request.thread_id}",
                success=False,
            )

        # Use existing thread
        client.beta.threads.messages.create(
            thread_id=request.thread_id, role="user", content=request.question
        )
    else:
        try:
            # Create new thread
            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id, role="user", content=request.question
            )
            request.thread_id = thread.id
        except openai.OpenAIError as e:
            # Handle any other OpenAI API errors
            if isinstance(e.body, dict) and "message" in e.body:
                error_message = e.body["message"]
            else:
                error_message = str(e)
            return AckPayload(
                status="error",
                message=error_message,
                success=False,
            )

    # 2. Send immediate response to complete the API call
    initial_response = AckPayload(
        status="processing",
        message="Run started",
        thread_id=request.thread_id,
        success=True,
    )

    # 3. Schedule the background task to run create_and_poll and send callback
    background_tasks.add_task(process_run, request, client)

    # 4. Return immediately so the client knows we've accepted the request
    return initial_response