"""LLM configuration models.

This module contains all configuration-related models for LLM requests,
including model specifications and advanced configuration options.
"""

from typing import Literal

from sqlmodel import SQLModel


class LLMModelSpec(SQLModel):
    """Specification for the LLM model and its parameters.

    This contains the actual model configuration that will be sent to the provider.
    Supports both standard models and advanced configurations.

    Attributes:
        model: Model identifier (e.g., "gpt-4", "claude-3-opus")
        provider: Provider type (openai, anthropic, google, azure)
        temperature: Sampling temperature (0.0-2.0)
        reasoning_effort: Reasoning effort level for o-series models ("low", "medium", "high")
        text_verbosity: Text verbosity level ("low", "medium", "high")
        max_tokens: Maximum number of tokens to generate
        top_p: Nucleus sampling parameter (0.0-1.0)
    """

    model: str
    provider: str = "openai"
    temperature: float | None = None
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    text_verbosity: Literal["low", "medium", "high"] | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class LLMConfig(SQLModel):
    """LLM configuration containing model specification and prompt.

    This wraps the model spec and can be extended with additional
    provider-agnostic configuration in the future.

    Attributes:
        prompt: The user's input prompt
        vector_store_id: Vector store ID for RAG functionality
        llm_model_spec: Model specification and parameters
    """

    prompt: str
    vector_store_id: str | None = None
    llm_model_spec: LLMModelSpec
