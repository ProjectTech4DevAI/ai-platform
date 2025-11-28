# safety/models.py
from pydantic import BaseModel
from typing import List, Dict, Any

class ValidatorItem(BaseModel):
    type: str
    params: Dict[str, Any] | None = None

class GuardrailConfig(BaseModel):
    guardrails: Dict[str, List[ValidatorItem]]