"""OpenAI provider implementation.

This module implements the BaseProvider interface for OpenAI models,
including support for standard models, o-series models with reasoning,
and file search capabilities.
"""

import logging
from typing import Any

import openai
from openai import OpenAI
from openai.types.responses.response import Response

from app.models.llm import LLMCallRequest, LLMCallResponse
from app.services.llm.base_provider import BaseProvider
from app.utils import handle_openai_error

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI implementation of the LLM provider.

    Supports:
    - Standard OpenAI models (GPT-4, GPT-3.5, etc.)
    - O-series models with reasoning configuration
    - Text configuration for verbosity control
    - Vector store file search integration
    """

    def __init__(self, client: OpenAI):
        """Initialize OpenAI provider with client.

        Args:
            client: OpenAI client instance
        """
        super().__init__(client)

    def supports_feature(self, feature: str) -> bool:
        """Check if OpenAI provider supports a specific feature.

        Args:
            feature: Feature name (reasoning, text_config, file_search, etc.)

        Returns:
            True if the feature is supported
        """
        supported_features = {
            "reasoning",
            "text_config",
            "file_search",
            "temperature",
            "max_tokens",
            "top_p",
        }
        return feature in supported_features

    def build_params(self, request: LLMCallRequest) -> dict[str, Any]:
        """Build OpenAI API parameters from LLMCallRequest.

        Converts our generic LLM config into OpenAI-specific parameters,
        including support for advanced features like reasoning and text configs.

        Args:
            request: LLM call request with configuration

        Returns:
            Dictionary of OpenAI API parameters
        """
        # Extract model spec for easier access
        model_spec = request.llm.llm_model_spec

        params: dict[str, Any] = {
            "model": model_spec.model,
            "input": [{"role": "user", "content": request.llm.prompt}],
        }

        # Add optional parameters if present
        if model_spec.temperature is not None:
            params["temperature"] = model_spec.temperature

        if model_spec.max_tokens is not None:
            params["max_tokens"] = model_spec.max_tokens

        if model_spec.top_p is not None:
            params["top_p"] = model_spec.top_p

        # Add advanced OpenAI configs (for o-series models, etc.)
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

    def _extract_file_search_results(self, response: Response) -> list[dict]:
        """Extract file search results from OpenAI response.

        Args:
            response: OpenAI response object

        Returns:
            List of dicts with 'score' and 'text' fields
        """
        results = []
        for tool_call in response.output:
            if tool_call.type == "file_search_call":
                results.extend(
                    {"score": hit.score, "text": hit.text} for hit in tool_call.results
                )
        return results

    def execute(
        self, request: LLMCallRequest
    ) -> tuple[LLMCallResponse | None, str | None]:
        """Execute OpenAI API call.

        Args:
            request: LLM call request with configuration

        Returns:
            Tuple of (response, error_message)
            - If successful: (LLMCallResponse, None)
            - If failed: (None, error_message)
        """
        response: Response | None = None
        error_message: str | None = None

        try:
            # Extract model spec for easier access
            model_spec = request.llm.llm_model_spec

            # Build parameters and make OpenAI call
            params = self.build_params(request)
            logger.info(
                f"[OpenAIProvider] Making OpenAI call with model: {model_spec.model}"
            )
            response = self.client.responses.create(**params)

            # Extract file search results if vector store was used
            file_search_results = None
            if request.llm.vector_store_id:
                file_search_results = self._extract_file_search_results(response)

            # Build response
            llm_response = LLMCallResponse(
                status="success",
                response_id=response.id,
                message=response.output_text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
                file_search_results=file_search_results,
            )

            logger.info(
                f"[OpenAIProvider] Successfully generated response: {response.id}"
            )
            return llm_response, None

        except openai.OpenAIError as e:
            error_message = handle_openai_error(e)
            logger.error(
                f"[OpenAIProvider] OpenAI API error: {error_message}", exc_info=True
            )
            return None, error_message

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            logger.error(f"[OpenAIProvider] {error_message}", exc_info=True)
            return None, error_message
