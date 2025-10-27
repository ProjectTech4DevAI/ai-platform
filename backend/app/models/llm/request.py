from typing import Any, Literal

from sqlmodel import Field, SQLModel
from pydantic import model_validator


class ConversationConfig(SQLModel):
    id: str | None = Field(
        default=None,
        description=(
            "Identifier for an existing conversation. "
            "Used to retrieve the previous message context and continue the chat. "
            "If not provided, a new conversation will be created."
        ),
    )
    auto_create: bool = Field(
        default=False,
        description=(
            "Only if True and no `id` is provided, a new conversation will be created automatically."
        ),
    )

    @model_validator(mode="after")
    def validate_conversation_logic(self):
        if self.id and self.auto_create:
            self.auto_create = False
        return self


# Query Parameters (dynamic per request)
class QueryParams(SQLModel):
    """Query-specific parameters for each LLM call."""

    input: str = Field(
        ...,
        min_length=1,
        description="User input question/query/prompt, used to generate a response.",
    )
    conversation: ConversationConfig | None = Field(
        default=None,
        description="Conversation control configuration for context handling.",
    )


class CompletionConfig(SQLModel):
    """Completion configuration with provider and parameters."""

    provider: Literal["openai"] = Field(
        default="openai", description="LLM provider to use"
    )
    params: dict[str, Any] = Field(
        ...,
        description="Provider-specific parameters (schema varies by provider), should exactly match the provider's endpoint params structure",
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
    config: LLMCallConfig = Field(..., description="Configuration for the LLM call")
    callback_url: str | None = Field(
        default=None, description="Webhook URL for async response delivery"
    )
    include_provider_response: bool = Field(
        default=False,
        description="Whether to include the raw LLM provider response in the output",
    )
