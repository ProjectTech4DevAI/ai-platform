from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

class ProviderType(str, Enum):
    OPENAI = "openai"
    LITELLM = "litellm"

class ModelType(str, Enum):
    GPT4_TURBO = "gpt-4-turbo-preview"
    GPT4 = "gpt-4"
    GPT35_TURBO = "gpt-3.5-turbo"

class AssistantRequest(BaseModel):
    name: str
    instructions: str
    model: ModelType = ModelType.GPT4_TURBO
    tools: Optional[List[Dict[str, Any]]] = None
    file_ids: Optional[List[str]] = None

class MessageRequest(BaseModel):
    content: str
    file_ids: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class RunRequest(BaseModel):
    assistant_id: str
    thread_id: str
    instructions: Optional[str] = None
    timeout: int = 300

class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: ModelType = ModelType.GPT4_TURBO
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False

class APIResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now) 