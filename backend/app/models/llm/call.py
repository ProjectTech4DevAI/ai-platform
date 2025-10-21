from typing import Optional, Literal
from sqlmodel import SQLModel


# Supported LLM providers
ProviderType = Literal["openai", "anthropic", "google", "azure"]


class ReasoningConfig(SQLModel):
    """Configuration for reasoning parameters (e.g., o-series models)."""

    effort: str  # "low", "medium", "high"


class TextConfig(SQLModel):
    """Configuration for text generation parameters."""

    verbosity: str  # "low", "medium", "high"


class LLMModelSpec(SQLModel):
    """Specification for the LLM model and its parameters.

    This contains the actual model configuration that will be sent to the provider.
    Supports both standard OpenAI models and advanced configurations.
    """

    model: str
    provider: ProviderType = "openai"  
    temperature: Optional[float] = None
    reasoning: Optional[ReasoningConfig] = None
    text: Optional[TextConfig] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None


class LLMConfig(SQLModel):
    """LLM configuration containing model specification.

    This wraps the model spec and can be extended with additional
    provider-agnostic configuration in the future.
    """
    prompt: str
    vector_store_id: Optional[str] = None
    llm_model_spec: LLMModelSpec


class LLMCallRequest(SQLModel):
    """Request model for /v1/llm/call endpoint.

    This model decouples LLM calls from the assistants table,
    allowing dynamic configuration per request.

    Structure:
    - llm: LLMConfig (contains model_spec)
    - prompt: The user's input
    - vector_store_id: Optional vector store for RAG
    - max_num_results: Number of results from vector store
    """

    llm: LLMConfig
    max_num_results: int = 20  # For vector store file search


class LLMCallResponse(SQLModel):
    """Response model for /v1/llm/call endpoint."""

    status: str
    response_id: str
    message: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    file_search_results: Optional[list[dict]] = None
