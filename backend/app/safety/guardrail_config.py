from sqlmodel import Field, SQLModel
from typing import List, Union, Annotated

from app.safety.validators.lexical_slur import LexicalSlurSafetyValidatorConfig

# todo this could be improved by having some auto-discovery mechanism inside
# validators. We'll not have to list every new validator like this. 
# from .validators.lexical_slur import LexicalSlurSafetyValidatorConfig


# class PIISafetyValidatorConfig(BaseValidatorConfig):
#     type: Literal["pii_remover"]
#     language: str = "en"
#     entity_types: List[str] = ["ALL"]
#     threshold: float = 0.5
#     # language_detector: Optional[LanguageDetector] = None
#     # validator_cls: ClassVar = <add-name>

# class GenderAssumptionBiasSafetyValidatorConfig(BaseValidatorConfig):
#     type: Literal["gender_assumption_bias"]
#     languages: List[str] = ["en", "hi"]
#     # validator_cls: ClassVar = <add-name>

ValidatorConfigItem = Annotated[
    # Union[PIISafetyValidatorConfig, LexicalSlurSafetyValidatorConfig, GenderAssumptionBiasSafetyValidatorConfig],
    Union[LexicalSlurSafetyValidatorConfig],
    Field(discriminator="type")
]

class GuardrailConfig(SQLModel):
    input: List[ValidatorConfigItem]
    output: List[ValidatorConfigItem]

class GuardrailConfigRoot(SQLModel):
    guardrails: GuardrailConfig
    # output: list[ValidatorUnion]