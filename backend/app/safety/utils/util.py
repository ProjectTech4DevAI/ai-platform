# safety/models.py
from pydantic import BaseModel
from typing import List, Dict, Any

from ..validators.piiremover import PIIRemover
from ..validators.lexicalslur import LexicalSlur

class ValidatorItem(BaseModel):
    type: str
    params: Dict[str, Any] | None = None

class GuardrailConfig(BaseModel):
    guardrails: Dict[str, List[ValidatorItem]]

VALIDATOR_REGISTRY = {
    "pii_remover": PIIRemover,
    "lexical_slur": LexicalSlur,
}