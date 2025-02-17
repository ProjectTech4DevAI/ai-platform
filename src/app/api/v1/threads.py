import os
import requests
import openai
from pydantic import BaseModel
from typing import Optional, List
from openai import OpenAI
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

router = APIRouter()


# Define the request body schema using Pydantic
class MessageRequest(BaseModel):
    question: str
    assistant_id: str
    callback_url: str
    thread_id: Optional[str] = None
    # Allow additional fields

    class Config:
        extra = "allow"


def send_callback(callback_url: str, data: dict):
    """Send results to the callback URL (synchronously)."""
    try:
        session = requests.Session()
        session.verify = False
        response = session.post(callback_url, json=data)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Callback failed: {str(e)}")
        return False


def process_run(request: MessageRequest, client: OpenAI):
    """
    Background task to run create_and_poll, then send the callback with the result.
    This function is run in the background after we have already returned an initial response.
    """
    try:
        # Start the run
        run = client.beta.threads.runs.create_and_poll(
            thread_id=request.thread_id,
            assistant_id=request.assistant_id,
        )

        if run.status == "completed":
            messages = client.beta.threads.messages.list(
                thread_id=request.thread_id)
            latest_message = messages.data[0]
            message_content = latest_message.content[0].text.value
            callback_response = {
                "status": "success",
                "message": message_content,
                "thread_id": request.thread_id,
                # Include any additional fields from request except the ones we don’t need to re-send
                **request.model_dump(exclude={"question", "assistant_id", "callback_url", "thread_id"}),
            }
        else:
            callback_response = {
                "status": "error",
                "message": f"Run failed with status: {run.status}",
                "thread_id": request.thread_id,
                **request.model_dump(exclude={"question", "assistant_id", "callback_url", "thread_id"}),
            }

        # Send callback with results
        send_callback(request.callback_url, callback_response)

    except openai.OpenAIError as e:
        # Handle any other OpenAI API errors
        error_str = str(e)
        if "'message': " in error_str:
            # Extract text between 'message': " and the next "
            start = error_str.find("'message': ") + len("'message': \"")
            end = error_str.find("\"", start)
            error_message = error_str[start:end]
        else:
            error_message = error_str

        callback_response = {
            "status": "error",
            "message": error_message,
            "thread_id": request.thread_id,
            **request.model_dump(exclude={"question", "assistant_id", "callback_url", "thread_id"}),
        }
        send_callback(request.callback_url, callback_response)


@router.post("/threads")
async def threads(request: MessageRequest, background_tasks: BackgroundTasks):
    """
    Accepts a question, assistant_id, callback_url, and optional thread_id from the request body.
    Returns an immediate "processing" response, then continues to run create_and_poll in background.
    Once completed, calls send_callback with the final result.
    """
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

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
            return {
                "status": "error",
                "message": f"Invalid thread ID provided {request.thread_id}",
            }

        # Use existing thread
        client.beta.threads.messages.create(
            thread_id=request.thread_id, role="user", content=request.question
        )
    else:
        # Create new thread
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=request.question
        )
        request.thread_id = thread.id

    # 2. Send immediate response to complete the API call
    initial_response = {
        "status": "processing",
        "message": "Run started",
        "thread_id": request.thread_id,
    }

    # 3. Schedule the background task to run create_and_poll and send callback
    background_tasks.add_task(process_run, request, client)

    # 4. Return immediately so the client knows we've accepted the request
    return initial_response
