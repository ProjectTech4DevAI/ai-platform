from guardrails import Guard
from guardrails.utils.validator_utils import get_validator
from app.safety.guardrail_config import GuardrailConfigRoot

class GuardrailsEngine():
    """
    Creates guardrails via user provided configuration.
    """
    def __init__(self, guardrail_config: GuardrailConfigRoot):
        # Ensure hub validators are auto-installed
        self._prepare_validators(guardrail_config.guardrails.input)
        self._prepare_validators(guardrail_config.guardrails.output)

        self.guardrail_config = guardrail_config

        # Now build guards
        self.input_guard = self._build_guard(self.guardrail_config.guardrails.input)
        self.output_guard = self._build_guard(self.guardrail_config.guardrails.output)

    def _prepare_validators(self, validator_items):
        for v_item in validator_items:
            post_init = getattr(v_item, "post_init", None)
            if post_init:
                post_init()  # Install hub validators & load class

    def _build_guard(self, validator_items):
        """
        Creates Guardrails AI `Guard`
        """
        validator_instances = []

        for v_item in validator_items:
            # Convert pydantic model -> kwargs for validator constructor
            params = v_item.model_dump()
            v_type = params.pop("type")

            # 1. Custom validator (has validator_cls)
            validator_cls = getattr(v_item, "validator_cls", None)
            if validator_cls:
                validator = validator_cls(**params)
                validator_instances.append(validator)
                continue

            validator_obj = get_validator({
            "type": v_type,
            **params
            })
            validator_instances.append(validator_obj)

        return Guard().use_many(*validator_instances)

    def run_input_validators(self, user_input: str):
        return self.input_guard.validate(user_input)

    def run_output_validators(self, llm_output: str):
        return self.output_guard.validate(llm_output)

