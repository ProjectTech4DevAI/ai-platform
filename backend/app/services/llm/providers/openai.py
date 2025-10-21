"""OpenAI provider implementation.

This module implements the BaseProvider interface for OpenAI models,
including support for standard models, o-series models with reasoning,
and file search capabilities.

Uses spec-based transformation for configuration conversion.
"""

import logging
from typing import Optional

import openai
from openai import OpenAI
from openai.types.responses.response import Response

from app.models.llm import LLMCallRequest, LLMCallResponse
from app.services.llm.providers.base import BaseProvider
from app.services.llm.transformers.base import ConfigTransformer
from app.utils import handle_openai_error

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI implementation of the LLM provider.

    Supports:
    - Standard OpenAI models (GPT-4, GPT-3.5, etc.)
    - O-series models with reasoning configuration
    - Text configuration for verbosity control
    - Vector store file search integration

    Uses OpenAITransformer for configuration conversion.
    """

    def __init__(self, client: OpenAI, transformer: Optional[ConfigTransformer] = None):
        """Initialize OpenAI provider with client and optional transformer.

        Args:
            client: OpenAI client instance
            transformer: Optional config transformer (will auto-create if not provided)
        """
        super().__init__(client, transformer)

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

        Uses the transformer to convert the request to OpenAI format,
        with automatic validation against model specs.

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

            # Build parameters using transformer (includes validation)
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

        except ValueError as e:
            error_message = f"Configuration validation failed: {str(e)}"
            logger.error(f"[OpenAIProvider] {error_message}", exc_info=True)
            return None, error_message

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
