"""OpenAI Responses API specification model.

This module defines the OpenAI-specific parameter specification with built-in
validation and conversion to API format based on the official OpenAI Responses API contract.

Reference: https://platform.openai.com/docs/api-reference/responses/create
"""

from typing import Any, Literal
import typing

from pydantic import Field, model_validator
from sqlmodel import SQLModel

from app.models.llm.request import CompletionConfig


class ReasoningConfig(SQLModel):
    """Configuration options for reasoning models (gpt-5 and o-series models only)."""

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


class FileSearchTool(SQLModel):
    """Tool configuration for searching through vector stores."""

    type: Literal["file_search"] = Field(
        default="file_search",
        description="The type of tool. Always 'file_search'.",
    )
    vector_store_ids: list[str] = Field(
        description="Vector store IDs to search through.",
    )
    max_num_results: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of results for file_search tool.",
    )


class OpenAIResponseSpec(SQLModel):
    """OpenAI Responses API specification with validation.

    This model defines all OpenAI Responses API parameters with their constraints,
    provides validation, and handles conversion to OpenAI API format.

    Aligns with OpenAI Responses API contract (POST https://api.openai.com/v1/responses).
    Reference: https://platform.openai.com/docs/api-reference/responses/create
    """

    model: str | None = Field(
        default="gpt-4o",
        description=(
            "Model ID used to generate the response, like gpt-4o or o3. "
            "OpenAI offers a wide range of models with different capabilities, performance characteristics, and price points."
        ),
    )

    input: str = Field(
        default=None,
        description=(
            "Text used to generate a response. "
            "Can be a simple text string (equivalent to a user role message), or a list of input items with different content types."
        ),
    )

    # Conversation
    conversation: str | None = Field(
        default=None,
        description=(
            "The conversation that this response belongs to. Items from this conversation are prepended to input_items. "
            "Can be a conversation ID (string) or a conversation object. Defaults to null."
        ),
    )

    previous_response_id: str | None = Field(
        default=None,
        description=(
            "The unique ID of the previous response to the model. Use this to create multi-turn conversations. "
            "Cannot be used in conjunction with conversation."
        ),
    )

    # Instructions & Context

    instructions: str | None = Field(
        default=None,
        description=(
            "A system (or developer) message inserted into the model's context. "
            "When using with previous_response_id, the instructions from a previous response will not be carried over."
        ),
    )
    include: Literal["file_search_call.results"] | None = Field(
        default=None,
        description=(
            "Specify additional output data to include in the model response. "
            "Currently supported values are: "
            "file_search_call.results, "
        ),
    )

    # Sampling Parameters

    temperature: float | None = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description=(
            "What sampling temperature to use, between 0 and 2. "
            "Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. "
            "We generally recommend altering this or top_p but not both."
        ),
    )

    top_p: float | None = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. "
            "So 0.1 means only the tokens comprising the top 10% probability mass are considered. "
            "We generally recommend altering this or temperature but not both."
        ),
    )

    max_output_tokens: int | None = Field(
        default=None,
        gt=0,
        description=(
            "An upper bound for the number of tokens that can be generated for a response, "
            "including visible output tokens and reasoning tokens."
        ),
    )

    # Tools (File Search Only)

    tools: list[FileSearchTool] | None = Field(
        default=None,
        description="File search tools for searching through vector stores.",
    )

    # Response Configuration

    reasoning: ReasoningConfig | None = Field(
        default=None,
        description=(
            "Configuration options for reasoning models (gpt-5 and o-series models only). "
            "Controls reasoning effort and summary generation."
        ),
    )

    truncation: Literal["auto", "disabled"] | None = Field(
        default="disabled",
        description=(
            "The truncation strategy to use for the model response. "
            "'auto': If input exceeds context window, truncate by dropping items from beginning. "
            "'disabled' (default): Request fails with 400 error if input exceeds context window."
        ),
    )

    # Advanced Options

    prompt_cache_key: str | None = Field(
        default=None,
        description=(
            "Used by OpenAI to cache responses for similar requests to optimize cache hit rates. "
        ),
    )

    @model_validator(mode="after")
    def validate_conversation_previous_response_exclusivity(
        self,
    ) -> "OpenAIResponseSpec":
        """Validate that conversation and previous_response_id are not used together.

        Returns:
            Self for method chaining

        Raises:
            ValueError: If both conversation and previous_response_id are provided
        """
        if self.conversation is not None and self.previous_response_id is not None:
            raise ValueError(
                "Cannot use both 'conversation' and 'previous_response_id' parameters together"
            )

        return self

    @model_validator(mode="after")
    def validate_temperature_top_p(self) -> "OpenAIResponseSpec":
        """Warn if both temperature and top_p are altered from defaults.

        Note: This is a soft validation (warning), not a hard error.

        Returns:
            Self for method chaining
        """
        # OpenAI recommends altering temperature OR top_p, but not both
        # We'll allow it but could log a warning in production
        if (
            self.temperature is not None
            and self.temperature != 1.0
            and self.top_p is not None
            and self.top_p != 1.0
        ):
            # In a production setting, you might want to log a warning here
            pass

        return self

    @classmethod
    def from_completion_config(cls, config: CompletionConfig) -> "OpenAIResponseSpec":
        """Convert generic CompletionConfig to OpenAI ResponseSpec.

        Args:
            config: Generic completion configuration

        Returns:
            OpenAI-specific response specification
        """
        # Build tools list if vector stores are provided
        tools = None
        if config.vector_store_ids:
            tools = [
                FileSearchTool(
                    vector_store_ids=config.vector_store_ids,
                    max_num_results=config.max_num_results,
                )
            ]

        # Convert ReasoningOptions to ReasoningConfig if provided
        reasoning = None
        if config.reasoning:
            reasoning = ReasoningConfig(
                effort=config.reasoning.effort,
                summary=config.reasoning.summary,
            )

        return cls(
            model=config.model,
            input=config.input,
            instructions=config.instructions,
            conversation=config.conversation_id,
            previous_response_id=config.previous_response_id,
            temperature=config.temperature,
            top_p=config.top_p,
            max_output_tokens=config.max_output_tokens,
            tools=tools,
            reasoning=reasoning,
        )

    def to_api_params(self) -> dict[str, Any]:
        """Convert OpenAIResponseSpec to OpenAI API parameters.

        Converts the spec to a dictionary suitable for passing to the OpenAI API,
        excluding None values and properly formatting nested objects.

        Returns:
            Dictionary of API parameters ready to be passed to openai.responses.create()
        """
        params = self.model_dump(exclude_none=True)

        print(params)

        return params
