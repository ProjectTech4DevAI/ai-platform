from pydantic import BaseModel, ConfigDict
from typing import Optional


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str
    assistant_id: str
    callback_url: str
    thread_id: Optional[str] = None
