import re
from .validator import Validator
from .utils.util import VALIDATOR_REGISTRY

class Guardrails():
    def __init__(self, guardrail_config):
        self.guardrail_config = guardrail_config
        self.input_validators = []
        self.output_validators = []

    def make(self):
        for validator_config in self.guardrail_config.guardrails.input:
            validator = self.build_validator(validator_config)
            self.input_validators.append(validator)

        for validator_config in self.guardrail_config.guardrails.output:
            validator = self.build_validator(validator_config)
            self.output_validators.append(validator)
        
    def build_validator(self, v_item):
        validator_cls = VALIDATOR_REGISTRY.get(v_item.type)
        if not validator_cls:
            raise ValueError(f"Unknown validator type: {v_item.type}")
        return validator_cls.make(v_item.dict())

    def run_input_validators(self, user_input):
        safe_input = user_input
        for validator in self.input_validators:
            safe_input = validator.execute(safe_input)
        return safe_input
    
    def run_output_validators(self, llm_output):
        safe_output = llm_output
        for validator in self.output_validators:
            safe_output = validator.execute(safe_output)
        return safe_output