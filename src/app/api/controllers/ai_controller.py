from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from ..dependencies import get_current_user, verify_api_key
from ...core.ai.models import (
    ProviderType, AssistantRequest, MessageRequest, 
    RunRequest, ChatCompletionRequest, APIResponse
)
from ...core.ai.assistant import AIAssistant

router = APIRouter(
    prefix="/api/v1",
    tags=["AI Assistant"],
    dependencies=[Depends(verify_api_key)]
)

@router.post("/assistants", 
    response_model=APIResponse,
    summary="Create a new AI Assistant",
    description="""
    Create a new AI Assistant with specified parameters.
    
    Example request:
    ```json
    {
        "name": "Research Assistant",
        "instructions": "You are a helpful research assistant.",
        "model": "gpt-4-turbo-preview",
        "tools": [],
        "file_ids": []
    }
    ```
    """
)
async def create_assistant(
    request: AssistantRequest,
    provider: Optional[ProviderType] = ProviderType.OPENAI
) -> APIResponse:
    ai = AIAssistant(provider=provider)
    return await ai.create_assistant(request)

@router.get("/assistants",
    response_model=APIResponse,
    summary="List all assistants",
    description="Retrieve a list of all available AI assistants."
)
async def list_assistants(
    limit: int = 20,
    provider: Optional[ProviderType] = ProviderType.OPENAI
) -> APIResponse:
    ai = AIAssistant(provider=provider)
    return await ai.list_assistants(limit)

@router.post("/threads/{thread_id}/messages",
    response_model=APIResponse,
    summary="Add message to thread",
    description="""
    Add a new message to an existing thread.
    
    Example request:
    ```json
    {
        "content": "What is the capital of France?",
        "file_ids": [],
        "metadata": {"user_id": "123"}
    }
    ```
    """
)
async def add_message(
    thread_id: str,
    request: MessageRequest,
    provider: Optional[ProviderType] = ProviderType.OPENAI
) -> APIResponse:
    ai = AIAssistant(provider=provider)
    return await ai.add_message(thread_id, request)

@router.post("/threads/{thread_id}/runs",
    response_model=APIResponse,
    summary="Run assistant on thread",
    description="""
    Run the AI assistant on a specific thread.
    
    Example request:
    ```json
    {
        "assistant_id": "asst_abc123",
        "thread_id": "thread_xyz789",
        "instructions": "Please be concise",
        "timeout": 300
    }
    ```
    """
)
async def run_assistant(
    thread_id: str,
    request: RunRequest,
    provider: Optional[ProviderType] = ProviderType.OPENAI
) -> APIResponse:
    if request.thread_id != thread_id:
        raise HTTPException(status_code=400, detail="Thread ID mismatch")
    ai = AIAssistant(provider=provider)
    return await ai.run_assistant(request)

@router.post("/chat/completions",
    response_model=APIResponse,
    summary="Chat completion",
    description="""
    Generate a chat completion response.
    
    Example request:
    ```json
    {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "model": "gpt-4-turbo-preview",
        "temperature": 0.7,
        "max_tokens": 150,
        "stream": false
    }
    ```
    """
)
async def chat_completion(
    request: ChatCompletionRequest,
    provider: Optional[ProviderType] = ProviderType.OPENAI
) -> APIResponse:
    ai = AIAssistant(provider=provider)
    return await ai.chat_completion(request)

@router.post("/threads",
    response_model=APIResponse,
    summary="Create a new thread",
    description="Create a new conversation thread."
)
async def create_thread(
    provider: Optional[ProviderType] = ProviderType.OPENAI
) -> APIResponse:
    ai = AIAssistant(provider=provider)
    result = await ai.create_thread()
    return APIResponse(success=True, data=result)

@router.get("/threads/{thread_id}/messages",
    response_model=APIResponse,
    summary="Get thread messages",
    description="Retrieve messages from a specific thread."
)
async def get_messages(
    thread_id: str,
    limit: int = 20,
    provider: Optional[ProviderType] = ProviderType.OPENAI
) -> APIResponse:
    ai = AIAssistant(provider=provider)
    return await ai.get_messages(thread_id, limit) 