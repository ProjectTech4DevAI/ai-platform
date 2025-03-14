from openai import AsyncOpenAI
from typing import Optional, Dict, Any
import asyncio
from app.core.config import settings


class AIAssistant:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def create_assistant(
        self,
        name: str,
        instructions: str,
        model: str = "gpt-4-turbo-preview",
        tools: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Create a new assistant with specified parameters"""
        try:
            assistant = await self.client.beta.assistants.create(
                name=name, instructions=instructions, model=model, tools=tools or []
            )
            return {
                "assistant_id": assistant.id,
                "name": assistant.name,
                "model": assistant.model,
                "created_at": assistant.created_at,
            }
        except Exception as e:
            return {"error": str(e)}

    async def create_thread(self) -> Dict[str, Any]:
        """Create a new thread for conversation"""
        try:
            thread = await self.client.beta.threads.create()
            return {"thread_id": thread.id}
        except Exception as e:
            return {"error": str(e)}

    async def add_message(self, thread_id: str, content: str) -> Dict[str, Any]:
        """Add a message to the thread"""
        try:
            message = await self.client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=content
            )
            return {"message_id": message.id}
        except Exception as e:
            return {"error": str(e)}

    async def run_assistant(
        self, assistant_id: str, thread_id: str, instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the assistant on the thread"""
        try:
            run = await self.client.beta.threads.runs.create(
                thread_id=thread_id, assistant_id=assistant_id, instructions=instructions
            )

            # Wait for completion
            while True:
                run_status = await self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run.id
                )
                if run_status.status == "completed":
                    break
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    return {"error": f"Run failed with status: {run_status.status}"}
                await asyncio.sleep(1)

            # Get messages after completion
            messages = await self.client.beta.threads.messages.list(thread_id=thread_id)

            # Get the latest assistant message
            for message in messages.data:
                if message.role == "assistant":
                    return {"response": message.content[0].text.value, "run_id": run.id}

            return {"error": "No assistant response found"}

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
                "created_at": assistant.created_at,
            }
        except Exception as e:
            return {"error": str(e)}