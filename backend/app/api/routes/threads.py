import re
import requests

from openai import OpenAI, OpenAIError
from fastapi import APIRouter, BackgroundTasks

from app.utils import APIResponse
from app.core import settings, logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["threads"])

class RequestCopier:
    _exclude = {
        "question",
        "assistant_id",
        "callback_url",
        "thread_id",
    }

    def __init__(self, request):
        self.request = request

    def __iter__(self):
        for (k, v) in self.request.items():
            if k not in self._exclude:
                yield (k, v)

def send_callback(callback_url: str, data: APIResponse):
    """Send results to the callback URL (synchronously)."""
    data = data.model_dump()
    try:
        session = requests.Session()
        # uncomment this to run locally without SSL
        # session.verify = False
        response = session.post(callback_url, json=data)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Callback failed: {e}")
        return False

def open_ai_error_to_string(error: OpenAIError):
    try:
        error_message = e.body["message"]
    except (AttributeError, TypeError, KeyError):
        error_message = str(error_message)

    return error_message

def process_run(request: dict, client: OpenAI):
    """
    Background task to run create_and_poll, then send the callback with the result.
    This function is run in the background after we have already returned an initial response.
    """

    thread_id = request["thread_id"]
    try:
        # Start the run
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=request["assistant_id"],
        )

        if run.status == "completed":
            messages = client.beta.threads.messages.list(thread_id=thread_id)
        else:
            error = f"Run failed with status: {run.status}"
            callback_response = APIResponse.failure_response(error)
            send_callback(request["callback_url"], callback_response)
    except OpenAIError as e:
        error = open_ai_error_to_string(e)
        callback_response = APIResponse.failure_response(error)
        send_callback(request["callback_url"], callback_response)

    message = messages.data[0].content[0].text.value

    remove_citation = request.get("remove_citation", False)
    if remove_citation:
        message = re.sub(r"【\d+(?::\d+)?†[^】]*】", "", message)

    copier = RequestCopier(request)
    additional_data = dict(copier)

    endpoint = getattr(request, "endpoint", "some-default-endpoint")

    callback_response = APIResponse.success_response(data={
        "status": "success",
        "message": message,
        "thread_id": thread_id,
        "endpoint": endpoint,
        **additional_data,
    })

    # Send callback with results
    send_callback(request["callback_url"], callback_response)


@router.post("/threads")
async def threads(request: dict, background_tasks: BackgroundTasks):
    """
    Accepts a question, assistant_id, callback_url, and optional thread_id from the request body.
    Returns an immediate "processing" response, then continues to run create_and_poll in background.
    Once completed, calls send_callback with the final result.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
 
    thread_id = request.get("thread_id")
    if thread_id is None:
        try:
            # Create new thread
            thread = client.beta.threads.create()
            thread_id = thread.id
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=request["question"],
            )
        except OpenAIError as e:
            error = open_ai_error_to_string(e)
            return APIResponse.failure_response(error=error)
        request["thread_id"] = thread_id

    # 2. Send immediate response to complete the API call
    initial_response = APIResponse.success_response(data={
        "status": "processing",
        "message": "Run started",
        "thread_id": thread_id,
        "success": True,
    })

    # 3. Schedule the background task to run create_and_poll and send callback
    background_tasks.add_task(process_run, request, client)

    # 4. Return immediately so the client knows we've accepted the request
    return initial_response
