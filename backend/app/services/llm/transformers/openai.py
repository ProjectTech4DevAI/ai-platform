"""OpenAI configuration transformer.

This module transforms unified API requests into OpenAI-specific format.
"""

from typing import Any, Optional

from app.models.llm import LLMCallRequest
from app.models.llm.specs import ModelSpec
from app.services.llm.transformers.base import ConfigTransformer


class OpenAITransformer(ConfigTransformer):
    """Transformer for OpenAI API format.

    Converts unified API contract to OpenAI Responses API format.
    Supports:
    - Standard models (GPT-4, GPT-3.5)
    - O-series models with reasoning configuration
    - Text configuration for verbosity control
    - Vector store file search integration
    """

    def __init__(self, model_spec: Optional[ModelSpec] = None):
        """Initialize OpenAI transformer.

        Args:
            model_spec: Optional model specification for validation
        """
        super().__init__(model_spec)

    def transform(self, request: LLMCallRequest) -> dict[str, Any]:
        """Transform request to OpenAI API parameters.

        Args:
            request: Unified LLM call request

        Returns:
            OpenAI API parameter dictionary
        """
        model_spec = request.llm.llm_model_spec

        # Base parameters
        params: dict[str, Any] = {
            "model": model_spec.model,
            "input": [{"role": "user", "content": request.llm.prompt}],
        }

        # Add optional standard parameters
        if model_spec.temperature is not None:
            params["temperature"] = model_spec.temperature

        if model_spec.max_tokens is not None:
            params["max_tokens"] = model_spec.max_tokens

        if model_spec.top_p is not None:
            params["top_p"] = model_spec.top_p

        # Add advanced OpenAI configs (o-series models)
        if model_spec.reasoning:
            params["reasoning"] = {"effort": model_spec.reasoning.effort}

        if model_spec.text:
            params["text"] = {"verbosity": model_spec.text.verbosity}

        # Add vector store file search if provided
        if request.llm.vector_store_id:
            params["tools"] = [
                {
                    "type": "file_search",
                    "vector_store_ids": [request.llm.vector_store_id],
                    "max_num_results": request.max_num_results,
                }
            ]
            params["include"] = ["file_search_call.results"]

        return params
