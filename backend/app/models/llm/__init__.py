"""LLM models module.

This module provides all data models for LLM functionality including
requests, responses, configurations, and model specifications.
"""

from app.models.llm.call import LLMCall, LLMCallCreate
from app.models.llm.config import (
    LLMConfig,
    LLMModelSpec,
    ProviderType,
    ReasoningConfig,
    TextConfig,
)
from app.models.llm.request import LLMCallRequest
from app.models.llm.response import LLMCallResponse
from app.models.llm.specs import (
    ModelCapabilities,
    ModelSpec,
    ModelSpecRegistry,
    ParameterSpec,
    model_spec_registry,
)

__all__ = [
    # Database models
    "LLMCall",
    "LLMCallCreate",
    # Request/Response models
    "LLMCallRequest",
    "LLMCallResponse",
    # Configuration models
    "LLMConfig",
    "LLMModelSpec",
    "ProviderType",
    "ReasoningConfig",
    "TextConfig",
    # Specification models
    "ModelSpec",
    "ModelCapabilities",
    "ParameterSpec",
    "ModelSpecRegistry",
    "model_spec_registry",
]
