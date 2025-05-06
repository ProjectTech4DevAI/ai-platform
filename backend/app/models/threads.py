from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class ThreadResponse(SQLModel, table=True):
    thread_id: str = Field(primary_key=True)
    message: Optional[str]
    question: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
