import logging

import openai
from openai import OpenAI
from openai.types.responses.response import Response

from app.models.llm import (
    CompletionConfig,
    LLMCallResponse,
    QueryParams,
)
from app.services.llm.providers.base import BaseProvider


logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    def __init__(self, client: OpenAI):
        """Initialize OpenAI provider with client.

        Args:
            client: OpenAI client instance
        """
        super().__init__(client)
        self.client = client

    def execute(
        self,
        completion_config: CompletionConfig,
        query: QueryParams,
        include_provider_response: bool = False,
    ) -> tuple[LLMCallResponse | None, str | None]:
        response: Response | None = None
        error_message: str | None = None

        try:
            params = {
                **completion_config.params,
            }
            params["input"] = query.input

            # Add conversation_id if provided
            if query.conversation_id:
                params["conversation_id"] = query.conversation_id

            response = self.client.responses.create(**params)

            # Build response
            llm_response = LLMCallResponse(
                id=response.id,
                output=response.output_text,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "model": response.model,
                    "provider": "openai",
                },
            )
            if include_provider_response:
                llm_response.llm_response = response.model_dump()

            logger.info(
                f"[OpenAIProvider.execute] Successfully generated response: {response.id}"
            )
            return llm_response, None

        except TypeError as e:
            # handle unexpected arguments gracefully
            error_message = f"Invalid or unexpected parameter in Config: {str(e)}"
            return None, error_message

        except openai.OpenAIError as e:
            # imported here to avoid circular imports
            from app.utils import handle_openai_error

            error_message = handle_openai_error(e)
            logger.error(
                f"[OpenAIProvider.execute] OpenAI API error: {error_message}", exc_info=True
            )
            return None, error_message

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            logger.error(f"[OpenAIProvider.execute] {error_message}", exc_info=True)
            return None, error_message
