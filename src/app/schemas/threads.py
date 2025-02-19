from pydantic import BaseModel
from typing import Optional


class MessageRequest(BaseModel):
    question: str
    assistant_id: str
    callback_url: str
    thread_id: Optional[str] = None
    # Allow additional fields

    class Config:
        extra = "allow"
