from typing import Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, ConfigDict
import requests
from openai import OpenAI, OpenAIError, NotFoundError
from app.core.config import settings
from app.core.logging import get_logger

# Initialize router and logger
router = APIRouter(prefix="/threads", tags=["threads"])
logger = get_logger(__name__)

# Request/Response Models
class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str
    assistant_id: str
    callback_url: str
    thread_id: Optional[str] = None

class AckPayload(BaseModel):
    status: str
    message: str
    success: bool
    thread_id: Optional[str] = None

class CallbackPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    message: str
    thread_id: str
    endpoint: str

def create_response(data: dict = None, error: str = None) -> dict:
    """Standardize API response format"""
    return {
        "success": error is None,
        "data": data,
        "error": error
    }

class ThreadService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def send_callback(self, callback_url: str, data: dict) -> bool:
        """Send results to the callback URL"""
        try:
            session = requests.Session()
            response = session.post(callback_url, json=data, timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"Callback failed: {str(e)}")
            return False

    def build_callback_payload(self, request: MessageRequest, status: str, message: str) -> CallbackPayload:
        """Build the CallbackPayload from a MessageRequest"""
        data = {
            "status": status,
            "message": message,
            "thread_id": request.thread_id,
            "endpoint": getattr(request, "endpoint", "default-endpoint"),
        }
        
        # Add additional fields from request
        data.update(
            request.model_dump(
                exclude={"question", "assistant_id", "callback_url", "thread_id"}
            )
        )
        
        return CallbackPayload(**data)

    async def process_run(self, request: MessageRequest):
        """Process the OpenAI run in background"""
        try:
            # Start the run
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=request.thread_id,
                assistant_id=request.assistant_id,
            )

            if run.status == "completed":
                messages = self.client.beta.threads.messages.list(thread_id=request.thread_id)
                latest_message = messages.data[0]
                message_content = latest_message.content[0].text.value
                callback_response = self.build_callback_payload(
                    request=request, 
                    status="success", 
                    message=message_content
                )
            else:
                callback_response = self.build_callback_payload(
                    request=request, 
                    status="error", 
                    message=f"Run failed with status: {run.status}"
                )

            await self.send_callback(request.callback_url, callback_response.model_dump())

        except OpenAIError as e:
            error_message = e.body.get("message", str(e)) if isinstance(e.body, dict) else str(e)
            callback_response = self.build_callback_payload(
                request=request, 
                status="error", 
                message=error_message
            )
            await self.send_callback(request.callback_url, callback_response.model_dump())

    async def validate_assistant(self, assistant_id: str) -> Optional[AckPayload]:
        """Validate assistant ID"""
        try:
            self.client.beta.assistants.retrieve(assistant_id=assistant_id)
            return None
        except NotFoundError:
            return AckPayload(
                status="error",
                message=f"Invalid assistant ID provided: {assistant_id}",
                success=False,
            )

    async def check_existing_run(self, thread_id: str) -> Optional[AckPayload]:
        """Check for existing runs on a thread"""
        try:
            runs = self.client.beta.threads.runs.list(thread_id=thread_id)
            if runs.data and runs.data[0].status in ["queued", "in_progress", "requires_action"]:
                return AckPayload(
                    status="error",
                    message=f"Active run exists (status: {runs.data[0].status})",
                    success=False,
                )
            return None
        except NotFoundError:
            return AckPayload(
                status="error",
                message=f"Invalid thread ID: {thread_id}",
                success=False,
            )

# Initialize service
thread_service = ThreadService()

@router.post("")
async def create_thread(
    request: MessageRequest, 
    background_tasks: BackgroundTasks
):
    """
    Create or use existing thread for AI assistant interaction
    """
    try:
        # Validate assistant
        assistant_error = await thread_service.validate_assistant(request.assistant_id)
        if assistant_error:
            return create_response(error=assistant_error.message)

        # Check existing thread
        if request.thread_id:
            run_error = await thread_service.check_existing_run(request.thread_id)
            if run_error:
                return create_response(error=run_error.message)
            
            # Add message to existing thread
            thread_service.client.beta.threads.messages.create(
                thread_id=request.thread_id,
                role="user",
                content=request.question
            )
        else:
            # Create new thread
            thread = thread_service.client.beta.threads.create()
            thread_service.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=request.question
            )
            request.thread_id = thread.id

        # Schedule background task
        background_tasks.add_task(thread_service.process_run, request)

        # Return immediate response
        return create_response(
            data={
                "status": "processing",
                "message": "Run started",
                "thread_id": request.thread_id,
                "success": True
            }
        )

    except OpenAIError as e:
        error_message = e.body.get("message", str(e)) if isinstance(e.body, dict) else str(e)
        logger.error(f"OpenAI error: {error_message}")
        return create_response(error=error_message)
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return create_response(error="Internal server error")