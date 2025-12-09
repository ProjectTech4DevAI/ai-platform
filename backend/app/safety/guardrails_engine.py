from guardrails import Guard
from guardrails.utils.validator_utils import get_validator
from app.safety.guardrail_config import GuardrailConfigRoot

class GuardrailsEngine():
    """
    Creates guardrails via user provided configuration.
    """
    def __init__(self, guardrail_config: GuardrailConfigRoot):
        # Ensure hub validators are auto-installed
        """
        Initialize the GuardrailsEngine by preparing validators and constructing input and output Guard instances.
        
        Prepares (and installs, if needed) any hub validators declared in the provided configuration, stores the configuration on the instance, and builds two Guard objects assigned to `self.input_guard` and `self.output_guard` for validating inputs and outputs respectively.
        
        Parameters:
            guardrail_config (GuardrailConfigRoot): Configuration containing `guardrails.input` and `guardrails.output` validator specifications used to prepare and build the validators and guards.
        """
        self._prepare_validators(guardrail_config.guardrails.input)
        self._prepare_validators(guardrail_config.guardrails.output)

        self.guardrail_config = guardrail_config

        # Now build guards
        self.input_guard = self._build_guard(self.guardrail_config.guardrails.input)
        self.output_guard = self._build_guard(self.guardrail_config.guardrails.output)

    def _prepare_validators(self, validator_items):
        """
        Ensure each validator item runs its optional post-initialization hook.
        
        Parameters:
            validator_items (Iterable): An iterable of validator configuration objects; for each item that defines a callable `post_init`, this method calls it so the validator can perform setup (for example, registering hub validators or loading classes).
        """
        for v_item in validator_items:
            post_init = getattr(v_item, "post_init", None)
            if post_init:
                post_init()  # Install hub validators & load class

    def _build_guard(self, validator_items):
        """
        Builds a Guard configured with validator instances described by validator_items.
        
        Each item is expected to be a pydantic model whose model_dump() produces constructor keyword arguments. If an item defines a `validator_cls` attribute that class will be instantiated with the remaining parameters; otherwise the item must include a `type` field used to create a validator from those parameters.
        
        Parameters:
            validator_items: An iterable of pydantic models that describe validators. Each model should include either a `validator_cls` attribute (a callable) or a `type` field in its dumped data.
        
        Returns:
            Guard: A Guard instance configured with all validator instances.
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
        """
        Run the input guard validators against the provided user input.
        
        Returns:
            validation_result: An object describing the validation outcome, including whether the input passed and any diagnostic details.
        """
        return self.input_guard.validate(user_input)

    def run_output_validators(self, llm_output: str):
        """
        Validate an LLM-generated output against the configured output validators.
        
        Parameters:
            llm_output (str): The text produced by the language model to be validated.
        
        Returns:
            validation_result: An object describing whether the output passed validation and any detected violations.
        """
        return self.output_guard.validate(llm_output)
