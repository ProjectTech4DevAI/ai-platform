from sqlmodel import Field, SQLModel
from typing import  List, Literal, Optional, Union, Annotated

# todo this could be improved by having some auto-discovery mechanism inside
# validators. We'll not have to list every new validator like this. 
# from .validators.lexical_slur import LexicalSlurSafetyValidatorConfig

class PIISafetyValidatorConfig(SQLModel):
    type: Literal["pii_remover"]
    language: str = "en"
    entity_types: List[str] = ["ALL"]
    threshold: float = 0.5

class GenderAssumptionBiasSafetyValidatorConfig(SQLModel):
    type: Literal["gender_assumption_bias"]
    languages: List[str] = ["en", "hi"]

class LexicalSlurSafetyValidatorConfig(SQLModel):
    type: Literal["uli_slur_match"]
    languages: List[str] = ["en", "hi"]
    severity: Literal["low", "medium", "high", "all"] = "all"


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