"""Custom exceptions for the LLM module.

This module defines all custom exceptions used throughout the LLM service layer,
providing better error handling and more descriptive error messages.
"""


class LLMServiceError(Exception):
    """Base exception for all LLM service errors."""

    pass


class ProviderError(LLMServiceError):
    """Raised when there's an error with the provider configuration or execution."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"Provider '{provider}' error: {message}")


class UnsupportedProviderError(ProviderError):
    """Raised when an unsupported provider is requested."""

    def __init__(self, provider: str, supported_providers: list[str]):
        self.supported_providers = supported_providers
        message = f"Unsupported provider. Supported: {', '.join(supported_providers)}"
        super().__init__(provider, message)


class ValidationError(LLMServiceError):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, parameter: str | None = None):
        self.parameter = parameter
        self.message = message
        error_msg = f"Validation error"
        if parameter:
            error_msg += f" for parameter '{parameter}'"
        error_msg += f": {message}"
        super().__init__(error_msg)


class TransformationError(LLMServiceError):
    """Raised when request transformation fails."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"Transformation error for {provider}: {message}")


class ModelSpecNotFoundError(LLMServiceError):
    """Raised when a model specification is not found."""

    def __init__(self, provider: str, model_name: str):
        self.provider = provider
        self.model_name = model_name
        super().__init__(
            f"Model spec not found for provider '{provider}', model '{model_name}'"
        )


class APICallError(LLMServiceError):
    """Raised when an API call to the provider fails."""

    def __init__(self, provider: str, message: str, original_error: Exception | None = None):
        self.provider = provider
        self.message = message
        self.original_error = original_error
        super().__init__(f"API call failed for {provider}: {message}")


class ParameterError(ValidationError):
    """Raised when there's an error with a specific parameter."""

    def __init__(self, parameter: str, message: str):
        super().__init__(message, parameter)


class RequiredParameterError(ParameterError):
    """Raised when a required parameter is missing."""

    def __init__(self, parameter: str):
        super().__init__(parameter, f"Required parameter '{parameter}' is missing")


class InvalidParameterTypeError(ParameterError):
    """Raised when a parameter has an invalid type."""

    def __init__(self, parameter: str, expected_type: str, actual_type: str):
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(
            parameter,
            f"Must be {expected_type}, got {actual_type}"
        )


class ParameterOutOfRangeError(ParameterError):
    """Raised when a parameter value is out of allowed range."""

    def __init__(self, parameter: str, value: float, min_value: float | None, max_value: float | None):
        self.value = value
        self.min_value = min_value
        self.max_value = max_value

        if min_value is not None and max_value is not None:
            msg = f"Value {value} is out of range [{min_value}, {max_value}]"
        elif min_value is not None:
            msg = f"Value {value} must be >= {min_value}"
        elif max_value is not None:
            msg = f"Value {value} must be <= {max_value}"
        else:
            msg = f"Value {value} is invalid"

        super().__init__(parameter, msg)


class InvalidParameterValueError(ParameterError):
    """Raised when a parameter has an invalid value."""

    def __init__(self, parameter: str, value: any, allowed_values: list):
        self.value = value
        self.allowed_values = allowed_values
        super().__init__(
            parameter,
            f"Value '{value}' is not allowed. Must be one of: {allowed_values}"
        )
