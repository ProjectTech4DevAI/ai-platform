"""OpenAI specification model.

This module defines the OpenAI-specific parameter specification with built-in
validation and conversion to API format.
"""

from typing import Any, Literal

from pydantic import Field, model_validator
from sqlmodel import SQLModel

from app.models.llm.request import LLMCallRequest


class OpenAISpec(SQLModel):
    """OpenAI Responses API specification with validation.

    This model defines all OpenAI Responses API parameters with their constraints,
    provides validation, and handles conversion to OpenAI API format.

    Aligns with OpenAI Responses API contract as of 2025.
    """

    # Required parameters
    model: str = Field(description="Model identifier (e.g., 'gpt-4o', 'gpt-4.1')")
    prompt: str = Field(description="User input prompt")

    # Sampling parameters
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature between 0.0 and 2.0",
    )
    max_output_tokens: int | None = Field(
        default=None, gt=0, description="Maximum tokens to generate (Responses API uses max_output_tokens)"
    )
    top_p: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling parameter"
    )

    # Advanced OpenAI-specific parameters
    reasoning_effort: Literal["low", "medium", "high"] | None = Field(
        default=None, description="Reasoning effort level for o-series models"
    )
    reasoning_generate_summary: bool | None = Field(
        default=None, description="Whether to generate reasoning summary for o-series models"
    )
    text_verbosity: Literal["low", "medium", "high"] | None = Field(
        default=None, description="Text verbosity level"
    )

    # Conversation and state management
    instructions: str | None = Field(
        default=None, description="System instructions for the model"
    )
    previous_response_id: str | None = Field(
        default=None, description="Previous response ID for conversation continuity"
    )
    store: bool | None = Field(
        default=None, description="Whether to store the conversation with OpenAI"
    )

    # Tool configuration
    parallel_tool_calls: bool | None = Field(
        default=None, description="Whether to enable parallel tool calls"
    )

    # Vector store file search
    vector_store_id: str | None = Field(
        default=None, description="Vector store ID for file search"
    )
    max_num_results: int | None = Field(
        default=None, ge=1, le=50, description="Max file search results"
    )

    # Response configuration
    truncation: Literal["auto", "disabled"] | None = Field(
        default=None, description="Truncation strategy for long contexts"
    )
    metadata: dict[str, str] | None = Field(
        default=None, description="Custom metadata for the request"
    )

    @model_validator(mode="after")
    def validate_vector_store(self) -> "OpenAISpec":
        """Validate vector store configuration.

        Ensures that if vector_store_id is provided, it's a valid non-empty string.

        Returns:
            Self for method chaining

        Raises:
            ValueError: If vector_store_id is invalid
        """
        if self.vector_store_id is not None and not self.vector_store_id.strip():
            raise ValueError("vector_store_id cannot be empty")
        return self

    def to_api_params(self) -> dict[str, Any]:
        """Convert to OpenAI Responses API parameters.

        Transforms this spec into the format expected by OpenAI's Responses API.
        Uses the official API contract with correct parameter names and structure.

        Returns:
            Dictionary of API parameters ready for openai.responses.create()
        """
        # Base parameters - always required
        params: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "user", "content": self.prompt}],
        }

        # Add optional sampling parameters
        if self.temperature is not None:
            params["temperature"] = self.temperature

        if self.max_output_tokens is not None:
            params["max_output_tokens"] = self.max_output_tokens

        if self.top_p is not None:
            params["top_p"] = self.top_p

        # Add conversation and state management
        if self.instructions is not None:
            params["instructions"] = self.instructions

        if self.previous_response_id is not None:
            params["previous_response_id"] = self.previous_response_id

        if self.store is not None:
            params["store"] = self.store

        # Add advanced OpenAI configurations
        if self.reasoning_effort is not None or self.reasoning_generate_summary is not None:
            reasoning_config: dict[str, Any] = {}
            if self.reasoning_effort is not None:
                reasoning_config["effort"] = self.reasoning_effort
            if self.reasoning_generate_summary is not None:
                reasoning_config["generate_summary"] = self.reasoning_generate_summary
            params["reasoning"] = reasoning_config

        if self.text_verbosity is not None:
            params["text"] = {"verbosity": self.text_verbosity}

        # Add tool configuration
        if self.parallel_tool_calls is not None:
            params["parallel_tool_calls"] = self.parallel_tool_calls

        # Add vector store file search if provided
        if self.vector_store_id:
            params["tools"] = [
                {
                    "type": "file_search",
                    "vector_store_ids": [self.vector_store_id],
                    "max_num_results": self.max_num_results or 20,
                }
            ]
            params["include"] = ["file_search_call.results"]

        # Add response configuration
        if self.truncation is not None:
            params["truncation"] = self.truncation

        if self.metadata is not None:
            params["metadata"] = self.metadata

        return params

    @classmethod
    def from_llm_request(cls, request: LLMCallRequest) -> "OpenAISpec":
        """Create OpenAISpec from LLMCallRequest.

        Convenience method to convert from the unified API request format.
        Maps the provider-agnostic max_tokens to OpenAI's max_output_tokens.

        Args:
            request: Unified LLM call request

        Returns:
            OpenAISpec instance
        """
        model_spec = request.llm.llm_model_spec

        return cls(
            model=model_spec.model,
            prompt=request.llm.prompt,
            temperature=model_spec.temperature,
            max_output_tokens=model_spec.max_tokens,  # Map max_tokens to max_output_tokens
            top_p=model_spec.top_p,
            reasoning_effort=model_spec.reasoning_effort,
            text_verbosity=model_spec.text_verbosity,
            vector_store_id=request.llm.vector_store_id,
            max_num_results=request.max_num_results,
        )
