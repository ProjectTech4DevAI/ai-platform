import argparse
from guardrails import Guard
import json
from sqlmodel import Field, SQLModel

from app.safety.guardrail_config import GuardrailConfigRoot

class GuardrailsEngine():
    def __init__(self, guardrail_config: SQLModel):
        self.guardrail_config = guardrail_config
        self.input_guard = None
        self.output_guard = None

    def make(self):
        self.input_guard = self.build_guard(self.guardrail_config.guardrails.input)
        self.output_guard = self.build_guard(self.guardrail_config.guardrails.output)

    def build_guard(self, validator_items):
        """
        Convert your config into Guard().use_many(*list_of_validators)
        """
        validator_instances = []

        for v_item in validator_items:
            validator_cls = v_item.validator_cls
            if not validator_cls:
                raise ValueError(f"Unknown validator type: {v_item.type}")
            print(v_item, validator_cls, end="\n")

            # # Convert pydantic model -> kwargs for validator constructor
            params = v_item.model_dump()
            params.pop("type")
            validator = validator_cls(**params)
            validator_instances.append(validator)

        return Guard().use_many(*validator_instances)

    def run_input_validators(self, user_input: str):
        if not self.input_guard:
            raise RuntimeError("Call make() before running validators.")
        return self.input_guard.validate(user_input)

    def run_output_validators(self, llm_output: str):
        if not self.output_guard:
            raise RuntimeError("Call make() before running validators.")
        return self.output_guard.validate(llm_output)

    def load_guardrail_config(self, guardrail_config):
        if isinstance(guardrail_config, GuardrailConfigRoot):
            return guardrail_config
    
        return GuardrailConfigRoot(**guardrail_config)