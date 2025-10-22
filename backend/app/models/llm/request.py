from sqlmodel import SQLModel, Field
from typing import Any, Literal
from pydantic import model_validator


class ReasoningOptions(SQLModel):
    """Configuration for reasoning models (o-series, gpt-5)."""

    effort: Literal["minimal", "low", "medium", "high"] | None = Field(
        default="medium",
        description=(
            "Constrains effort on reasoning for reasoning models. "
            "Reducing reasoning effort can result in faster responses and fewer tokens used. "
            "Note: The gpt-5-pro model defaults to (and only supports) high reasoning effort."
        ),
    )
    summary: Literal["auto", "concise", "detailed"] | None = Field(
        default=None,
        description=(
            "A summary of the reasoning performed by the model. "
            "This can be useful for debugging and understanding the model's reasoning process."
        ),
    )


class CompletionConfig(SQLModel):
    """Generic LLM completion configuration supporting multiple providers."""

    provider: Literal["openai"] = Field(
        default="openai", description="LLM provider to use"
    )
    model: str = Field(
        default="gpt-4o",
        min_length=1,
        description="Model name/identifier to use for completion",
    )

    input: str = Field(
        ..., min_length=1, description="User input text/prompt for the model"
    )

    # RAG
    vector_store_ids: list[str] | None = Field(
        default=None, description="Vector store IDs to search through."
    )
    max_num_results: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of results for RAG. Applies when vector_store_ids are provided.",
    )

    # Context
    instructions: str | None = Field(
        default=None, description="System instructions/prompt for the model"
    )

    conversation_id: str | None = Field(
        default=None, description="Conversation ID to continue existing conversation"
    )

    previous_response_id: str | None = Field(
        default=None,
        description="ID of previous response for multi-turn conversations (mutually exclusive with conversation)",
    )

    # Response Configuration
    reasoning: ReasoningOptions | None = Field(
        default=None,
        description="Reasoning configuration for models with reasoning capabilities (o-series, etc.)",
    )

    # Sampling Parameters
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description=(
            "Sampling temperature (0-2): higher = more random, lower = more deterministic"
            "We generally recommend altering this or top_p but not both."
        ),
    )

    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Nucleus sampling: consider tokens with top_p probability mass"
            "We generally recommend altering this or temperature but not both."
        ),
    )

    max_output_tokens: int | None = Field(
        default=None, gt=0, description="Maximum tokens to generate in the response."
    )

    # Validators
    @model_validator(mode="after")
    def validate_conversation_exclusivity(self) -> "CompletionConfig":
        """Ensure conversation_id and previous_response_id are not used together."""
        if self.conversation_id is not None and self.previous_response_id is not None:
            raise ValueError(
                "Cannot use both 'conversation_id' and 'previous_response_id' together"
            )
        return self

    @model_validator(mode="after")
    def vector_store_list_not_empty(self) -> "CompletionConfig":
        """Ensure vector_store_ids is not an empty list if provided."""
        if self.vector_store_ids is not None and len(self.vector_store_ids) == 0:
            raise ValueError("'vector_store_ids' cannot be an empty list")
        return self


class LLMConfig(SQLModel):
    completion: CompletionConfig = Field(..., description="Completion configuration")


class LLMCallRequest(SQLModel):
    """User-facing API request for LLM completion."""

    config: LLMConfig
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata for tracking and context"
    )
