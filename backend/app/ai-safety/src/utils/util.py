# safety/models.py
from pydantic import BaseModel, Field
from typing import Callable, List, Literal, Optional, Union
from guardrails import OnFailAction
from ..utils.languagedetector import LanguageDetector

# ----------------------------------------
# Validator-specific config models
# ----------------------------------------
class BaseValidatorConfig(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True
    }

class PIISafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["pii_remover"]
    language: str = "en"
    entity_types: List[str] = ["ALL"]
    threshold: float = 0.5
    language_detector: Optional[LanguageDetector] = None
    on_fail: Optional[Callable] = OnFailAction.FIX

class LexicalSlurSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["lexical_slur"]
    languages: List[str] = ["en", "hi"]
    severity: Literal["low", "medium", "high", "all"] = "all"
    on_fail: Optional[Callable] = OnFailAction.FIX

class GenderAssumptionBiasSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["gender_assumption_bias"]
    languages: List[str] = ["en", "hi"]
    on_fail: Optional[Callable] = OnFailAction.FIX

# ----------------------------------------
# Discriminated Union
# ----------------------------------------

ValidatorUnion = Union[
    PIISafetyValidatorConfig,
    LexicalSlurSafetyValidatorConfig,
    GenderAssumptionBiasSafetyValidatorConfig,
]

class GuardrailConfig(BaseModel):
    guardrails: dict[str, list[ValidatorUnion]]