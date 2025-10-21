"""Constants and type definitions for the LLM module.

This module centralizes all constants, enums, and type definitions used
across the LLM service layer.
"""

from typing import Literal

# Provider type definitions
ProviderType = Literal["openai"]

# Reasoning effort levels for o-series models
EffortLevel = Literal["low", "medium", "high"]

# Text verbosity levels
VerbosityLevel = Literal["low", "medium", "high"]

# Job status
JobStatusType = Literal["pending", "processing", "success", "failed"]

# Default parameter values
DEFAULT_TEMPERATURE = 1.0
DEFAULT_TOP_P = 1.0
DEFAULT_MAX_RESULTS = 20

# Parameter constraints
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0
MIN_TOP_P = 0.0
MAX_TOP_P = 1.0
MIN_MAX_TOKENS = 1
MAX_MAX_TOKENS = 128000

# Supported providers
SUPPORTED_PROVIDERS = ["openai"]

# Error messages
ERROR_UNSUPPORTED_PROVIDER = "Provider '{provider}' is not supported. Supported: {supported}"
ERROR_VALIDATION_FAILED = "Configuration validation failed: {details}"
ERROR_TRANSFORMATION_FAILED = "Failed to transform request: {details}"
ERROR_API_CALL_FAILED = "API call failed: {details}"
ERROR_UNKNOWN_PARAMETER = "Unknown parameter '{param}' for model {model}"
ERROR_REQUIRED_PARAMETER = "Required parameter '{param}' is missing"
ERROR_INVALID_TYPE = "Parameter '{param}' must be {expected_type}"
ERROR_OUT_OF_RANGE = "Parameter '{param}' must be between {min_val} and {max_val}"
ERROR_INVALID_VALUE = "Parameter '{param}' must be one of {allowed_values}"

# Feature names for capability checks
FEATURE_REASONING = "reasoning"
FEATURE_TEXT_CONFIG = "text_config"
FEATURE_FILE_SEARCH = "file_search"
FEATURE_FUNCTION_CALLING = "function_calling"
FEATURE_STREAMING = "streaming"
FEATURE_VISION = "vision"
