"""LLM configuration models.

This module contains all configuration-related models for LLM requests,
including model specifications and advanced configuration options.
"""

from typing import Literal, Optional

from sqlmodel import SQLModel

# Type definitions
ProviderType = Literal["openai", "anthropic", "google", "azure"]


class ReasoningConfig(SQLModel):
    """Configuration for reasoning parameters (e.g., o-series models).

    Attributes:
        effort: Reasoning effort level - "low", "medium", or "high"
    """

    effort: str  # "low", "medium", "high"


class TextConfig(SQLModel):
    """Configuration for text generation parameters.

    Attributes:
        verbosity: Text verbosity level - "low", "medium", or "high"
    """

    verbosity: str  # "low", "medium", "high"


class LLMModelSpec(SQLModel):
    """Specification for the LLM model and its parameters.

    This contains the actual model configuration that will be sent to the provider.
    Supports both standard models and advanced configurations.

    Attributes:
        model: Model identifier (e.g., "gpt-4", "claude-3-opus")
        provider: Provider type (openai, anthropic, google, azure)
        temperature: Sampling temperature (0.0-2.0)
        reasoning: Optional reasoning configuration for o-series models
        text: Optional text verbosity configuration
        max_tokens: Maximum number of tokens to generate
        top_p: Nucleus sampling parameter (0.0-1.0)
    """

    model: str
    provider: ProviderType = "openai"
    temperature: Optional[float] = None
    reasoning: Optional[ReasoningConfig] = None
    text: Optional[TextConfig] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None


class LLMConfig(SQLModel):
    """LLM configuration containing model specification and prompt.

    This wraps the model spec and can be extended with additional
    provider-agnostic configuration in the future.

    Attributes:
        prompt: The user's input prompt
        vector_store_id: Optional vector store ID for RAG functionality
        llm_model_spec: Model specification and parameters
    """

    prompt: str
    vector_store_id: Optional[str] = None
    llm_model_spec: LLMModelSpec
