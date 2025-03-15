from fastapi import APIRouter, HTTPException
from typing import Optional, Any, Dict
from pydantic import BaseModel
from typing import Optional, List
from app.core.ai_assistant import AIAssistant

router = APIRouter(prefix="/ai-assistant", tags=["ai-assistant"])

class AssistantCreate(BaseModel):
    name: str
    instructions: str
    model: str = "gpt-4-turbo-preview"
    tools: Optional[List[dict]] = None


class MessageCreate(BaseModel):
    content: str
def create_response(data: Any = None, error: str = None) -> Dict:
    """
    Standardize API response format
    
    Args:
        data: The data to be returned
        error: Error message if any
    
    Returns:
        Dict with standardized format:
        {
            "success": bool,
            "data": Any | None,
            "error": str | None
        }
    """
    return {
        "success": error is None,
        "data": data,
        "error": error
    }

@router.post("/create-assistant")
async def create_assistant(data: AssistantCreate):
    try:
        ai = AIAssistant()
        result = await ai.create_assistant(
        name=data.name, instructions=data.instructions, model=data.model, tools=data.tools
        )
        return create_response(data=result)
    except Exception as e:
        return create_response(error=str(e))


@router.post("/chat/{assistant_id}")
async def chat_with_assistant(assistant_id: str, message: MessageCreate):
    ai = AIAssistant()

    # Create a thread
    thread_result = await ai.create_thread()
    if "error" in thread_result:
        raise HTTPException(status_code=400, detail=thread_result["error"])

    thread_id = thread_result["thread_id"]

    # Add message to thread
    message_result = await ai.add_message(thread_id, message.content)
    if "error" in message_result:
        raise HTTPException(status_code=400, detail=message_result["error"])

    # Run assistant
    response = await ai.run_assistant(assistant_id, thread_id)
    if "error" in response:
        raise HTTPException(status_code=400, detail=response["error"])

    return response