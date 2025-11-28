import argparse
import json
from .utils.validator_registry import VALIDATOR_REGISTRY
from .utils.util import GuardrailConfig

class Guardrails():
    def __init__(self, guardrail_config_path):        
        self.guardrail_config = self.load_guardrail_config(guardrail_config_path)
        self.input_validators = []
        self.output_validators = []

    def make(self):
        for validator_config in self.guardrail_config.guardrails["input"]:
            validator = self.build_validator(validator_config)
            self.input_validators.append(validator)

        for validator_config in self.guardrail_config.guardrails["output"]:
            validator = self.build_validator(validator_config)
            self.output_validators.append(validator)
        
    def build_validator(self, v_item):
        validator_cls = VALIDATOR_REGISTRY.get(v_item.type)
        if not validator_cls:
            raise ValueError(f"Unknown validator type: {v_item["type"]}")
        
        validator_instance = validator_cls(v_item)
        return validator_instance

    def run_input_validators(self, user_input):
        safe_input = user_input
        for validator in self.input_validators:
            safe_input = validator._validate(safe_input)
            print("Detected: ", safe_input)
        return safe_input
    
    def run_output_validators(self, llm_output):
        safe_output = llm_output
        for validator in self.output_validators:
            safe_output = validator._validate(safe_output)
        return safe_output
    
    def load_guardrail_config(self, path):
        with open(path, "r") as f:
            data = json.load(f)
        config = GuardrailConfig(**data)
        return config