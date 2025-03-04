from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from ...core.ai.assistant import AIAssistant

router = APIRouter()


class AssistantCreate(BaseModel):
    name: str
    instructions: str
    model: str = "gpt-4-turbo-preview"
    tools: Optional[List[dict]] = None


class MessageCreate(BaseModel):
    content: str


@router.post("/create-assistant")
async def create_assistant(data: AssistantCreate):
    ai = AIAssistant()
    result = await ai.create_assistant(
        name=data.name, instructions=data.instructions, model=data.model, tools=data.tools
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/chat/{assistant_id}")
async def chat_with_assistant(
    assistant_id: str, 
    message: MessageCreate, 
    project_id: Optional[str] = None
):
    ai = AIAssistant(project_id=project_id)

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
