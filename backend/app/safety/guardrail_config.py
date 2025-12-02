from sqlmodel import Field, SQLModel
from typing import List, Union, Annotated

# todo this could be improved by having some auto-discovery mechanism inside
# validators. We'll not have to list every new validator like this.
from app.safety.validators.lexical_slur import LexicalSlurSafetyValidatorConfig 

ValidatorConfigItem = Annotated[
    # future validators
    # Union[PIISafetyValidatorConfig, LexicalSlurSafetyValidatorConfig, GenderAssumptionBiasSafetyValidatorConfig],
    Union[LexicalSlurSafetyValidatorConfig],
    Field(discriminator="type")
]

class GuardrailConfig(SQLModel):
    input: List[ValidatorConfigItem]
    output: List[ValidatorConfigItem]

class GuardrailConfigRoot(SQLModel):
    guardrails: GuardrailConfig