"""OpenAI specification model.

This module defines the OpenAI-specific parameter specification with built-in
validation and conversion to API format.
"""

from typing import Any, Literal

from pydantic import Field, model_validator
from sqlmodel import SQLModel

from app.models.llm.request import LLMCallRequest


class OpenAISpec(SQLModel):
    """OpenAI API specification with validation.

    This model defines all OpenAI-specific parameters with their constraints,
    provides validation, and handles conversion to OpenAI API format.

    Attributes:
        model: Model identifier (e.g., "gpt-4", "gpt-3.5-turbo", "o1-preview")
        prompt: The user's input prompt
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum number of tokens to generate (must be positive)
        top_p: Nucleus sampling parameter (0.0-1.0)
        reasoning_effort: Optional reasoning effort level for o-series models ("low", "medium", "high")
        text_verbosity: Optional text verbosity level ("low", "medium", "high")
        vector_store_id: Optional vector store ID for file search
        max_num_results: Maximum number of file search results (1-50)
    """

    # Required parameters
    model: str = Field(description="Model identifier")
    prompt: str = Field(description="User input prompt")

    # Optional standard parameters
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature between 0.0 and 2.0",
    )
    max_tokens: int | None = Field(
        default=None, gt=0, description="Maximum tokens to generate"
    )
    top_p: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling parameter"
    )

    # Advanced OpenAI-specific parameters
    reasoning_effort: Literal["low", "medium", "high"] | None = Field(
        default=None, description="Reasoning effort level for o-series models"
    )
    text_verbosity: Literal["low", "medium", "high"] | None = Field(
        default=None, description="Text verbosity level"
    )

    # Vector store file search
    vector_store_id: str | None = Field(
        default=None, description="Vector store ID for file search"
    )
    max_num_results: int | None = Field(
        default=None, ge=1, le=50, description="Max file search results"
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
        """Convert to OpenAI API parameters.

        Transforms this spec into the format expected by OpenAI's Responses API.

        Returns:
            Dictionary of API parameters ready for openai.responses.create()
        """
        # Base parameters - always required
        params: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "user", "content": self.prompt}],
        }

        # Add optional standard parameters
        if self.temperature is not None:
            params["temperature"] = self.temperature

        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens

        if self.top_p is not None:
            params["top_p"] = self.top_p

        # Add advanced OpenAI configurations
        if self.reasoning_effort is not None:
            params["reasoning"] = {"effort": self.reasoning_effort}

        if self.text_verbosity is not None:
            params["text"] = {"verbosity": self.text_verbosity}

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

        return params

    @classmethod
    def from_llm_request(cls, request: "LLMCallRequest") -> "OpenAISpec":
        """Create OpenAISpec from LLMCallRequest.

        Convenience method to convert from the unified API request format.

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
            max_tokens=model_spec.max_tokens,
            top_p=model_spec.top_p,
            reasoning_effort=model_spec.reasoning_effort,
            text_verbosity=model_spec.text_verbosity,
            vector_store_id=request.llm.vector_store_id,
            max_num_results=request.max_num_results,
        )
