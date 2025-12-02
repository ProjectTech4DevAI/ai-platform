from guardrails import Guard
from app.safety.guardrail_config import GuardrailConfigRoot

class GuardrailsEngine():
    """
    Creates guardrails via user provided configuration.
    """
    def __init__(self, guardrail_config: GuardrailConfigRoot):
        self.guardrail_config = guardrail_config
        self.input_guard = self._build_guard(self.guardrail_config.guardrails.input)
        self.output_guard = self._build_guard(self.guardrail_config.guardrails.output)

    def _build_guard(self, validator_items):
        """
        Creates Guardrails AI `Guard`
        """
        validator_instances = []

        for v_item in validator_items:
            validator_cls = v_item.validator_cls
            if not validator_cls:
                raise ValueError(f"Unknown validator type: {v_item.type}")
            # print(v_item, validator_cls, end="\n")

            # # Convert pydantic model -> kwargs for validator constructor
            params = v_item.model_dump()
            params.pop("type")
            validator = validator_cls(**params)
            validator_instances.append(validator)

        return Guard().use_many(*validator_instances)

    def run_input_validators(self, user_input: str):
        return self.input_guard.validate(user_input)

    def run_output_validators(self, llm_output: str):
        return self.output_guard.validate(llm_output)

