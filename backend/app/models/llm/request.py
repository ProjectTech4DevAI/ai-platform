from sqlmodel import SQLModel, Field
from typing import Any, Literal


# Query Parameters (dynamic per request)
class QueryParams(SQLModel):
    """Query-specific parameters for each LLM call."""

    input: str = Field(..., min_length=1, description="User input text/prompt")
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation ID. If not provided, a new conversation will be created.",
    )


class CompletionConfig(SQLModel):
    """Completion configuration with provider and parameters."""

    provider: Literal["openai"] = Field(
        default="openai", description="LLM provider to use"
    )
    params: dict[str, Any] = Field(
        ..., description="Provider-specific parameters (schema varies by provider)"
    )


class LLMCallConfig(SQLModel):
    """Complete configuration for LLM call including all processing stages."""

    completion: CompletionConfig = Field(..., description="Completion configuration")
    # Future additions:
    # classifier: ClassifierConfig | None = None
    # pre_filter: PreFilterConfig | None = None


class LLMCallRequest(SQLModel):
    """User-facing API request for LLM completion."""

    query: QueryParams = Field(..., description="Query-specific parameters")
    config: LLMCallConfig = Field(
        ..., description="Configuration for the LLM call"
    )
    callback_url: str | None = Field(
        default=None, description="Webhook URL for async response delivery"
    )
