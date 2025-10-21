"""OpenAI provider implementation.

This module implements the BaseProvider interface for OpenAI models,
including support for standard models, o-series models with reasoning,
and file search capabilities.

Uses OpenAISpec for parameter validation and API conversion.
"""

import logging

import openai
from openai import OpenAI
from openai.types.responses.response import Response
from pydantic import ValidationError

from app.models.llm import LLMCallRequest, LLMCallResponse
from app.services.llm.providers.base import BaseProvider
from app.services.llm.specs import OpenAISpec
from app.utils import handle_openai_error

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI implementation of the LLM provider.

    Supports:
    - Standard OpenAI models (GPT-4, GPT-3.5, etc.)
    - O-series models with reasoning configuration
    - Text configuration for verbosity control
    - Vector store file search integration

    Uses OpenAISpec for parameter validation and conversion.
    """

    def __init__(self, client: OpenAI):
        """Initialize OpenAI provider with client.

        Args:
            client: OpenAI client instance
        """
        super().__init__(client)
        self.client = client

    def execute(
        self, request: LLMCallRequest
    ) -> tuple[LLMCallResponse | None, str | None]:
        """Execute OpenAI API call.

        Uses OpenAISpec to validate and convert the request to OpenAI format.

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
            # Create and validate OpenAI spec from request
            spec = OpenAISpec.from_llm_request(request)

            # Convert to API parameters (validation happens during spec creation)
            params = spec.to_api_params()

            logger.info(f"[OpenAIProvider] Making OpenAI call with model: {spec.model}")
            response = self.client.responses.create(**params)

            # Build response
            llm_response = LLMCallResponse(
                status="success",
                response_id=response.id,
                message=response.output_text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
            )

            logger.info(
                f"[OpenAIProvider] Successfully generated response: {response.id}"
            )
            return llm_response, None

        except ValidationError as e:
            error_message = f"Configuration validation failed: {str(e)}"
            logger.error(f"[OpenAIProvider] {error_message}", exc_info=True)
            return None, error_message

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
