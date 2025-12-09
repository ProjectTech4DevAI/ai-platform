from typing import ClassVar, List, Literal

from app.safety.validators.base_validator_config import BaseValidatorConfig
from app.safety.validators.constants import BAN_LIST
from app.safety.validators.hub_loader import load_hub_validator_class, ensure_hub_validator_installed

class BanListSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal[f"{BAN_LIST}"]
    banned_words: List[str]
    validator_cls: ClassVar = None

    def post_init(self):
        # Ensure installed before we load class
        """
        Verify the ban-list hub validator is available and load its validator class into the class-level `validator_cls`.
        
        Ensures the hub-backed ban-list validator is installed, then sets the class variable `validator_cls` to the loaded validator class so instances can use the hub implementation.
        """
        ensure_hub_validator_installed(BAN_LIST)
        self.__class__.validator_cls = load_hub_validator_class(BAN_LIST)