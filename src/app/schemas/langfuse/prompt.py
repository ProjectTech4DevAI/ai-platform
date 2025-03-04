from datetime import datetime
from typing import List, Dict, Optional, Union, Literal
from pydantic import BaseModel, Field

# To validate list of prompts
class PromptMeta(BaseModel):
    name: str
    versions: List[int]
    labels: List[str]
    tags: List[str]
    last_updated_at: datetime = Field(..., alias="lastUpdatedAt")
    last_config: Dict = Field(..., alias="lastConfig")

class MetaResponse(BaseModel):
    page: int
    limit: int
    total_items: int = Field(..., alias="totalItems")
    total_pages: int = Field(..., alias="totalPages")

class PromptMetaListResponse(BaseModel):
    data: List[PromptMeta]
    meta: MetaResponse

class PromptQueryParams(BaseModel):
    name: Optional[str] = None
    label: Optional[str] = None
    tag: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1)
    from_updated_at: Optional[datetime] = None
    to_updated_at: Optional[datetime] = None

# Chat message schema for chat prompts
class ChatMessage(BaseModel):
    role: str
    content: str

# Common fields for both chat and text prompts
class BasePrompt(BaseModel):
    name: str = Field(..., example="example-prompt")
    version: int = Field(..., example=1)
    config: Dict = Field(..., example={"temperature": 0.7})
    labels: List[str] = Field(..., example=["latest", "production"], description="List of deployment labels for this version.")
    tags: List[str] = Field(..., example=["tag1", "tag2"], description="List of tags used for filtering across versions.")
    commit_message: Optional[str] = Field(None, alias="commitMessage", example="Initial version", description="Commit message for this prompt version.")

# Chat-based prompt schema
class ChatPromptCreate(BasePrompt):
    type: Literal["chat"] = Field("chat", example="chat")
    prompt: List[ChatMessage] = Field(..., example=[{"role": "user", "content": "Hello!"}])

# Text-based prompt schema
class TextPromptCreate(BasePrompt):
    type: Literal["text"] = Field("text", example="text")
    prompt: str = Field(..., example="Write a short story about AI.")

# Union type for handling both prompt types
PromptDetailResponse = Union[ChatPromptCreate, TextPromptCreate]

# Request model for creating prompts with required fields
PromptCreateRequest = Union[ChatPromptCreate, TextPromptCreate]
