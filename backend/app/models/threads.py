from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, UTC


class OpenAIThreadBase(SQLModel):
    thread_id: str = Field(index=True, unique=True)
    prompt: str
    response: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


class OpenAIThreadCreate(OpenAIThreadBase):
    pass  # Used for requests, no `id` or timestamps


class OpenAI_Thread(OpenAIThreadBase, table=True):
    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
