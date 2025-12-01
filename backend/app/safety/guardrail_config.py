from guardrails import OnFailAction
from sqlmodel import Field, SQLModel
from typing import Callable, ClassVar, List, Literal, Optional, Union, Annotated

# from .utils.language_detector import LanguageDetector
from .validators.lexical_slur import LexicalSlur

# todo this could be improved by having some auto-discovery mechanism inside
# validators. We'll not have to list every new validator like this. 
# from .validators.lexical_slur import LexicalSlurSafetyValidatorConfig

class BaseValidatorConfig(SQLModel):
    # override in subclasses
    validator_cls: ClassVar = None
    on_fail: Optional[Callable] = OnFailAction.FIX

class PIISafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["pii_remover"]
    language: str = "en"
    entity_types: List[str] = ["ALL"]
    threshold: float = 0.5
    # language_detector: Optional[LanguageDetector] = None
    # validator_cls: ClassVar = <add-name>

class GenderAssumptionBiasSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["gender_assumption_bias"]
    languages: List[str] = ["en", "hi"]
    # validator_cls: ClassVar = <add-name>
    
class LexicalSlurSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["uli_slur_match"]
    languages: List[str] = ["en", "hi"]
    severity: Literal["low", "medium", "high", "all"] = "all"
    validator_cls: ClassVar = LexicalSlur


ValidatorConfigItem = Annotated[
    Union[PIISafetyValidatorConfig, LexicalSlurSafetyValidatorConfig, GenderAssumptionBiasSafetyValidatorConfig],
    Field(discriminator="type")
]

class GuardrailConfig(SQLModel):
    input: List[ValidatorConfigItem]
    output: List[ValidatorConfigItem]

class GuardrailConfigRoot(SQLModel):
    guardrails: GuardrailConfig
    # output: list[ValidatorUnion]