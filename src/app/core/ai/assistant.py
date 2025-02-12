from typing import Optional, Dict, Any, List, Union
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
from litellm import AsyncLiteLLM
from .models import (
    ProviderType, AssistantRequest, MessageRequest, 
    RunRequest, ChatCompletionRequest, APIResponse
)
from ..config import settings

class AIClient:
    """Factory for creating AI clients"""
    @staticmethod
    def create_client(provider: ProviderType):
        if provider == ProviderType.OPENAI:
            return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        elif provider == ProviderType.LITELLM:
            return AsyncLiteLLM(api_key=settings.OPENAI_API_KEY)
        raise ValueError(f"Unsupported provider: {provider}")

class AIAssistant:
    def __init__(self, provider: ProviderType = ProviderType.OPENAI):
        """Initialize the AI Assistant with specified provider"""
        self.provider = provider
        self.client = AIClient.create_client(provider)
        
    async def create_assistant(self, request: AssistantRequest) -> APIResponse:
        """Create a new assistant with specified parameters"""
        try:
            assistant = await self.client.beta.assistants.create(
                name=request.name,
                instructions=request.instructions,
                model=request.model.value,
                tools=request.tools or [],
                file_ids=request.file_ids or []
            )
            return APIResponse(
                success=True,
                data={
                    "assistant_id": assistant.id,
                    "name": assistant.name,
                    "model": assistant.model,
                    "created_at": assistant.created_at
                }
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    async def list_assistants(self, limit: int = 20) -> APIResponse:
        """List all assistants"""
        try:
            assistants = await self.client.beta.assistants.list(limit=limit)
            return APIResponse(
                success=True,
                data={
                    "assistants": [{
                        "assistant_id": ast.id,
                        "name": ast.name,
                        "model": ast.model,
                        "created_at": ast.created_at
                    } for ast in assistants.data]
                }
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    async def add_message(self, thread_id: str, request: MessageRequest) -> APIResponse:
        """Add a message to the thread"""
        try:
            message = await self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=request.content,
                file_ids=request.file_ids or [],
                metadata=request.metadata
            )
            return APIResponse(
                success=True,
                data={
                    "message_id": message.id,
                    "created_at": message.created_at
                }
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    async def run_assistant(self, request: RunRequest) -> APIResponse:
        """Run the assistant on the thread"""
        try:
            run = await self.client.beta.threads.runs.create(
                thread_id=request.thread_id,
                assistant_id=request.assistant_id,
                instructions=request.instructions
            )
            
            start_time = datetime.now()
            while True:
                run_status = await self.client.beta.threads.runs.retrieve(
                    thread_id=request.thread_id,
                    run_id=run.id
                )
                
                if run_status.status == 'completed':
                    break
                elif run_status.status in ['failed', 'cancelled', 'expired']:
                    return APIResponse(
                        success=False,
                        error=f"Run failed with status: {run_status.status}",
                        data={"run_id": run.id}
                    )
                
                if (datetime.now() - start_time).seconds > request.timeout:
                    await self.client.beta.threads.runs.cancel(
                        thread_id=request.thread_id,
                        run_id=run.id
                    )
                    return APIResponse(
                        success=False,
                        error="Run timed out",
                        data={"run_id": run.id}
                    )
                
                await asyncio.sleep(1)

            messages = await self.client.beta.threads.messages.list(
                thread_id=request.thread_id,
                limit=1,
                order="desc"
            )
            
            if messages.data:
                message = messages.data[0]
                if message.role == "assistant":
                    return APIResponse(
                        success=True,
                        data={
                            "response": message.content[0].text.value,
                            "run_id": run.id,
                            "message_id": message.id,
                            "created_at": message.created_at
                        }
                    )
            
            return APIResponse(success=False, error="No assistant response found")
            
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    async def chat_completion(self, request: ChatCompletionRequest) -> APIResponse:
        """Generic chat completion that works with both OpenAI and LiteLLM"""
        try:
            response = await self.client.chat.completions.create(
                model=request.model.value,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=request.stream
            )
            
            return APIResponse(
                success=True,
                data={
                    "response": response.choices[0].message.content,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    async def create_thread(self) -> Dict[str, Any]:
        """Create a new thread for conversation"""
        try:
            thread = await self.client.beta.threads.create()
            return {"thread_id": thread.id}
        except Exception as e:
            return {"error": str(e)}

    async def get_assistant(self, assistant_id: str) -> Dict[str, Any]:
        """Get assistant details"""
        try:
            assistant = await self.client.beta.assistants.retrieve(assistant_id)
            return {
                "assistant_id": assistant.id,
                "name": assistant.name,
                "model": assistant.model,
                "created_at": assistant.created_at
            }
        except Exception as e:
            return {"error": str(e)} 