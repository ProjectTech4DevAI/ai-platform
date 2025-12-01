from sqlmodel import Field, SQLModel
from typing import Callable, ClassVar, List, Literal, Optional, Union
from guardrails import OnFailAction
from ..utils.language_detector import LanguageDetector
from ..validators.pii_remover import PIIRemover
from ..validators.lexical_slur import LexicalSlur

# ----------------------------------------
# Validator-specific config models
# ----------------------------------------
# class BaseValidatorConfig(BaseModel):
#     model_config = {
#         "arbitrary_types_allowed": True
#     }

#     # override in subclasses
#     validator_cls: ClassVar = None

class PIISafetyValidatorConfig(SQLModel):
    type: Literal["pii_remover"]
    language: str = "en"
    entity_types: List[str] = ["ALL"]
    threshold: float = 0.5
    language_detector: Optional[LanguageDetector] = None
    on_fail: Optional[Callable] = OnFailAction.FIX
    validator_cls: ClassVar = PIIRemover

class LexicalSlurSafetyValidatorConfig(SQLModel):
    type: Literal["uli_slur_match"]
    languages: List[str] = ["en", "hi"]
    severity: Literal["low", "medium", "high", "all"] = "all"
    on_fail: Optional[Callable] = OnFailAction.FIX
    validator_cls: ClassVar = LexicalSlur

class GenderAssumptionBiasSafetyValidatorConfig(SQLModel):
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