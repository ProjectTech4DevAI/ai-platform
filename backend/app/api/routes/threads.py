import openai
import re
import requests
from openai import OpenAI
from fastapi import APIRouter, BackgroundTasks
from app.utils import APIResponse
from app.core import settings, logging

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


def process_run(request: dict, client: OpenAI):
    """
    Background task to run create_and_poll, then send the callback with the result.
    This function is run in the background after we have already returned an initial response.
    """
    try:
        # Start the run
        run = client.beta.threads.runs.create_and_poll(
            thread_id=request["thread_id"],
            assistant_id=request["assistant_id"],
        )

        if run.status == "completed":
            messages = client.beta.threads.messages.list(
                thread_id=request["thread_id"])
            latest_message = messages.data[0]
            message_content = latest_message.content[0].text.value

            if request["remove_citation"]:
                message = re.sub(r"【\d+(?::\d+)?†[^】]*】", "", message_content)
            else:
                message = message_content

            # Update the data dictionary with additional fields from the request, excluding specific keys
            additional_data = {k: v for k, v in request.items(
            ) if k not in {"question", "assistant_id", "callback_url", "thread_id"}}
            callback_response = APIResponse.success_response(data={
                "status": "success",
                "message": message,
                "thread_id": request["thread_id"],
                "endpoint": getattr(request, "endpoint", "some-default-endpoint"),
                **additional_data
            })
        else:
            callback_response = APIResponse.failure_response(
                error=f"Run failed with status: {run.status}")

        # Send callback with results
        send_callback(request["callback_url"], callback_response.model_dump())

    except openai.OpenAIError as e:
        # Handle any other OpenAI API errors
        if isinstance(e.body, dict) and "message" in e.body:
            error_message = e.body["message"]
        else:
            error_message = str(e)

        callback_response = APIResponse.failure_response(error=error_message)

        send_callback(request["callback_url"], callback_response.model_dump())


def validate_assistant_id(assistant_id: str, client: OpenAI):
    try:
        client.beta.assistants.retrieve(assistant_id=assistant_id)
    except openai.NotFoundError:
        return APIResponse.failure_response(error=f"Invalid assistant ID provided {assistant_id}")
    return None


@router.post("/threads")
async def threads(request: dict, background_tasks: BackgroundTasks):
    """
    Accepts a question, assistant_id, callback_url, and optional thread_id from the request body.
    Returns an immediate "processing" response, then continues to run create_and_poll in background.
    Once completed, calls send_callback with the final result.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    assistant_error = validate_assistant_id(request["assistant_id"], client)
    if assistant_error:
        return assistant_error

    # Use get method to safely access thread_id
    thread_id = request.get("thread_id")

    # 1. Validate or check if there's an existing thread with an in-progress run
    if thread_id:
        try:
            runs = client.beta.threads.runs.list(thread_id=thread_id)
            # Get the most recent run (first in the list) if any
            if runs.data and len(runs.data) > 0:
                latest_run = runs.data[0]
                if latest_run.status in ["queued", "in_progress", "requires_action"]:
                    return APIResponse.failure_response(error=f"There is an active run on this thread (status: {latest_run.status}). Please wait for it to complete.")
        except openai.OpenAIError:
            # Handle invalid thread ID
            return APIResponse.failure_response(error=f"Invalid thread ID provided {thread_id}")

        # Use existing thread
        client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=request["question"]
        )
    else:
        try:
            # Create new thread
            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id, role="user", content=request["question"]
            )
            request["thread_id"] = thread.id
        except openai.OpenAIError as e:
            # Handle any other OpenAI API errors
            if isinstance(e.body, dict) and "message" in e.body:
                error_message = e.body["message"]
            else:
                error_message = str(e)
            return APIResponse.failure_response(error=error_message)

    # 2. Send immediate response to complete the API call
    initial_response = APIResponse.success_response(data={
        "status": "processing",
        "message": "Run started",
        "thread_id": request.get("thread_id"),
        "success": True,
    })

    # 3. Schedule the background task to run create_and_poll and send callback
    background_tasks.add_task(process_run, request, client)

    # 4. Return immediately so the client knows we've accepted the request
    return initial_response
