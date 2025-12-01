from guardrails import OnFailAction
from sqlmodel import Field, SQLModel
from typing import Callable, ClassVar, Optional

class BaseValidatorConfig(SQLModel):
    # override in subclasses
    validator_cls: ClassVar = None
    on_fail: Optional[Callable] = OnFailAction.FIX
