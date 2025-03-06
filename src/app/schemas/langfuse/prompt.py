from datetime import datetime
from typing import List, Dict, Optional, Literal, Union
from pydantic import BaseModel, Field, model_validator


# Chat message schema
class ChatMessage(BaseModel):
    role: str
    content: str


# Unified prompt schema with conditional validation
class PromptCreateRequest(BaseModel):
    name: str = Field(..., example="example-prompt", description="The unique name of the prompt.")
    type: Literal["text", "chat"] = Field(..., example="text", description="The type of prompt: 'text' for a single string, 'chat' for a conversation history.")
    prompt: Union[str, List[ChatMessage]] = Field(..., description="For 'text' type, provide a string. For 'chat' type, provide a list of messages.")
    config: Optional[Dict] = Field(None, example={"temperature": 0.7}, description="Configuration settings for the prompt execution.")
    labels: Optional[List[str]] = Field(None, example=["latest", "production"], description="List of deployment labels for this version.")
    tags: Optional[List[str]] = Field(None, example=["tag1", "tag2"], description="List of tags used for filtering across versions.")
    commit_message: Optional[str] = Field(None, alias="commitMessage", example="Initial version", description="Commit message for this prompt version.")

    @model_validator(mode="before")
    def validate_prompt(cls, values):
        prompt_type = values.get("type")
        prompt_value = values.get("prompt")

        if prompt_type == "chat":
            if not isinstance(prompt_value, list) or not all(isinstance(msg, dict) and "role" in msg and "content" in msg for msg in prompt_value):
                raise ValueError("For 'chat' type, 'prompt' must be a list of ChatMessage dictionaries.")
        elif prompt_type == "text":
            if not isinstance(prompt_value, str):
                raise ValueError("For 'text' type, 'prompt' must be a string.")
        return values


# Response model for retrieving prompts
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


class PromptDetailResponse(PromptCreateRequest):
    version: int = Field(..., example=1, description="Version number of the prompt.")
