import logging
import warnings
from datetime import datetime, timezone

from fastapi import HTTPException
from requests import Session, RequestException
from pydantic import BaseModel, HttpUrl
from langfuse import Langfuse
from langfuse.decorators import langfuse_context
from openai import OpenAI

logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def raise_from_unknown(error: Exception, status_code=500):
    logger.warning(
        'Unexpected exception "{}": {}'.format(
            type(error).__name__,
            error,
        )
    )
    raise HTTPException(status_code=status_code, detail=str(error))


def post_callback(url: HttpUrl, payload: BaseModel):
    errno = 0
    with Session() as session:
        response = session.post(str(url), json=payload.model_dump())
        try:
            response.raise_for_status()
        except RequestException as err:
            logger.warning(f"Callback failure: {err}")
            errno += 1

    return not errno


def configure_langfuse(credentials: dict) -> tuple[Langfuse, bool]:
    """
    Configure Langfuse client and context with the provided credentials.

    Args:
        credentials: Dictionary containing Langfuse credentials (public_key, secret_key, host)

    Returns:
        Tuple of (Langfuse client instance, success boolean)
    """
    if not credentials:
        return None, False

    try:
        # Configure Langfuse client
        langfuse = Langfuse(
            public_key=credentials["public_key"],
            secret_key=credentials["secret_key"],
            host=credentials.get("host", "https://cloud.langfuse.com"),
        )

        # Configure Langfuse context
        langfuse_context.configure(
            secret_key=credentials["secret_key"],
            public_key=credentials["public_key"],
            host=credentials.get("host", "https://cloud.langfuse.com"),
        )

        return langfuse, True
    except Exception as e:
        logger.error(f"Failed to configure Langfuse: {str(e)}")
        return None, False


def configure_openai(credentials: dict) -> tuple[OpenAI, bool]:
    """
    Configure OpenAI client with the provided credentials.

    Args:
        credentials: Dictionary containing OpenAI credentials (api_key)

    Returns:
        Tuple of (OpenAI client instance, success boolean)
    """
    if not credentials or "api_key" not in credentials:
        return None, False

    try:
        # Configure OpenAI client
        client = OpenAI(api_key=credentials["api_key"])
        return client, True
    except Exception as e:
        logger.error(f"Failed to configure OpenAI client: {str(e)}")
        return None, False
