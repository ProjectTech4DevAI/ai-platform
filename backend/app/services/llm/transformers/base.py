"""Base configuration transformer for LLM providers.

This module provides the transformation logic to convert from the unified
API contract to provider-specific configurations. It uses model specs to
guide the transformation and validation process.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.llm import LLMCallRequest
from app.models.llm.specs import ModelSpec, model_spec_registry


class ConfigTransformer(ABC):
    """Base class for provider-specific config transformers.

    Each provider (OpenAI, Anthropic, etc.) should implement a transformer
    that knows how to convert our unified API contract into that provider's
    specific API format.

    Attributes:
        model_spec: Optional model specification for validation
    """

    def __init__(self, model_spec: Optional[ModelSpec] = None):
        """Initialize transformer with optional model spec.

        Args:
            model_spec: Optional model specification for validation
        """
        self.model_spec = model_spec

    @abstractmethod
    def transform(self, request: LLMCallRequest) -> dict[str, Any]:
        """Transform unified request to provider-specific parameters.

        Args:
            request: Unified LLM call request

        Returns:
            Provider-specific parameter dictionary

        Raises:
            ValueError: If transformation fails or validation errors occur
        """
        raise NotImplementedError("Transformers must implement transform method")

    def validate_and_transform(self, request: LLMCallRequest) -> dict[str, Any]:
        """Validate request against model spec and transform.

        Args:
            request: Unified LLM call request

        Returns:
            Provider-specific parameter dictionary

        Raises:
            ValueError: If validation fails
        """
        # If we have a model spec, validate the config
        if self.model_spec:
            config = {
                "model": request.llm.llm_model_spec.model,
                "provider": request.llm.llm_model_spec.provider,
                "temperature": request.llm.llm_model_spec.temperature,
                "max_tokens": request.llm.llm_model_spec.max_tokens,
                "top_p": request.llm.llm_model_spec.top_p,
            }

            # Add advanced configs if present
            if request.llm.llm_model_spec.reasoning:
                config["reasoning"] = request.llm.llm_model_spec.reasoning.effort

            if request.llm.llm_model_spec.text:
                config["text"] = request.llm.llm_model_spec.text.verbosity

            # Validate against spec
            is_valid, error_msg = self.model_spec.validate_config(config)
            if not is_valid:
                raise ValueError(f"Configuration validation failed: {error_msg}")

        # Perform transformation
        return self.transform(request)
