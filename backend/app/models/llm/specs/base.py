"""Base model specification classes.

This module defines the schema for LLM model specifications that declare:
- What parameters each model supports
- Valid ranges and types for parameters
- Provider-specific capabilities
- Validation rules for configurations
"""

from typing import Any, Literal, Optional

from pydantic import Field
from sqlmodel import SQLModel


# Parameter type definitions
EffortLevel = Literal["low", "medium", "high"]
VerbosityLevel = Literal["low", "medium", "high"]


class ParameterSpec(SQLModel):
    """Specification for a single parameter.

    Attributes:
        name: Parameter name
        type: Parameter type (str, int, float, bool)
        required: Whether parameter is required
        default: Default value if not provided
        min_value: Minimum value for numeric parameters
        max_value: Maximum value for numeric parameters
        allowed_values: List of allowed values for enum-like parameters
        description: Human-readable parameter description
    """

    name: str = Field(description="Parameter name")
    type: str = Field(description="Parameter type (str, int, float, bool)")
    required: bool = Field(default=False, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value")
    min_value: Optional[float] = Field(
        default=None, description="Minimum value for numeric params"
    )
    max_value: Optional[float] = Field(
        default=None, description="Maximum value for numeric params"
    )
    allowed_values: Optional[list[Any]] = Field(
        default=None, description="List of allowed values"
    )
    description: Optional[str] = Field(default=None, description="Parameter description")


class ModelCapabilities(SQLModel):
    """Capabilities supported by a model.

    Attributes:
        supports_reasoning: Whether the model supports reasoning configuration
        supports_text_config: Whether the model supports text verbosity config
        supports_file_search: Whether the model supports vector store file search
        supports_function_calling: Whether the model supports function calling
        supports_streaming: Whether the model supports streaming responses
        supports_vision: Whether the model supports image inputs
    """

    supports_reasoning: bool = Field(
        default=False, description="Supports reasoning configuration"
    )
    supports_text_config: bool = Field(
        default=False, description="Supports text verbosity config"
    )
    supports_file_search: bool = Field(
        default=False, description="Supports vector store file search"
    )
    supports_function_calling: bool = Field(
        default=False, description="Supports function calling"
    )
    supports_streaming: bool = Field(
        default=False, description="Supports streaming responses"
    )
    supports_vision: bool = Field(default=False, description="Supports image inputs")


class ModelSpec(SQLModel):
    """Complete specification for an LLM model.

    This is the single source of truth for what a model supports.
    It defines capabilities, parameter constraints, and validation rules.

    Attributes:
        model_name: Model identifier (e.g., 'gpt-4', 'claude-3-opus')
        provider: Provider name (openai, anthropic, google, azure)
        capabilities: What features this model supports
        parameters: List of supported parameters with their constraints
    """

    model_config = {"protected_namespaces": ()}  # Allow model_ prefix

    model_name: str = Field(
        description="Model identifier (e.g., 'gpt-4', 'claude-3-opus')"
    )
    provider: str = Field(description="Provider name (openai, anthropic, google, azure)")
    capabilities: ModelCapabilities = Field(
        description="What features this model supports"
    )
    parameters: list[ParameterSpec] = Field(
        default_factory=list, description="Supported parameters"
    )

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate a configuration against this model spec.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
            - If valid: (True, None)
            - If invalid: (False, error_message)
        """
        # Build parameter lookup
        param_specs = {p.name: p for p in self.parameters}

        # Check for unknown parameters
        for key in config.keys():
            if key not in param_specs and key not in [
                "model",
                "provider",
                "prompt",
                "vector_store_id",
            ]:
                return False, f"Unknown parameter '{key}' for model {self.model_name}"

        # Validate each parameter
        for param_spec in self.parameters:
            value = config.get(param_spec.name)

            # Check required parameters
            if param_spec.required and value is None:
                return False, f"Required parameter '{param_spec.name}' is missing"

            # Skip validation if value is None and not required
            if value is None:
                continue

            # Type validation
            if param_spec.type == "int" and not isinstance(value, int):
                return False, f"Parameter '{param_spec.name}' must be an integer"
            elif param_spec.type == "float" and not isinstance(value, (int, float)):
                return False, f"Parameter '{param_spec.name}' must be a number"
            elif param_spec.type == "bool" and not isinstance(value, bool):
                return False, f"Parameter '{param_spec.name}' must be a boolean"
            elif param_spec.type == "str" and not isinstance(value, str):
                return False, f"Parameter '{param_spec.name}' must be a string"

            # Range validation for numeric types
            if param_spec.type in ["int", "float"]:
                if param_spec.min_value is not None and value < param_spec.min_value:
                    return (
                        False,
                        f"Parameter '{param_spec.name}' must be >= {param_spec.min_value}",
                    )
                if param_spec.max_value is not None and value > param_spec.max_value:
                    return (
                        False,
                        f"Parameter '{param_spec.name}' must be <= {param_spec.max_value}",
                    )

            # Allowed values validation
            if param_spec.allowed_values is not None and value not in param_spec.allowed_values:
                return (
                    False,
                    f"Parameter '{param_spec.name}' must be one of {param_spec.allowed_values}",
                )

        return True, None

    def supports_feature(self, feature: str) -> bool:
        """Check if this model supports a specific feature.

        Args:
            feature: Feature name to check

        Returns:
            True if feature is supported
        """
        feature_map = {
            "reasoning": self.capabilities.supports_reasoning,
            "text_config": self.capabilities.supports_text_config,
            "file_search": self.capabilities.supports_file_search,
            "function_calling": self.capabilities.supports_function_calling,
            "streaming": self.capabilities.supports_streaming,
            "vision": self.capabilities.supports_vision,
        }
        return feature_map.get(feature, False)
