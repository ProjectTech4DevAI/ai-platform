import logging
import warnings
from datetime import datetime, timezone

from fastapi import HTTPException
from requests import Session, RequestException
from pydantic import BaseModel, HttpUrl
from langfuse import Langfuse
from langfuse.decorators import langfuse_context
from openai import OpenAI


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def raise_from_unknown(error: Exception, status_code=500):
    warnings.warn(
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
            warnings.warn(f"Callback failure: {err}")
            errno += 1

    return not errno


def configure_langfuse(credentials: dict, enabled: bool) -> tuple[Langfuse, bool]:
    """
    Configure Langfuse client and context with the provided credentials and tracing status.

    Args:
        credentials: Dictionary containing Langfuse credentials (public_key, secret_key, host)
        enabled: Boolean to enable/disable Langfuse tracing.

    Returns:
        Tuple of (Langfuse client instance, success boolean)
    """
    try:
        if credentials:
            # If credentials exist, configure Langfuse client and enable tracing
            # Configure Langfuse client
            langfuse = Langfuse(
                public_key=credentials["public_key"],
                secret_key=credentials["secret_key"],
                host=credentials.get("host", "https://cloud.langfuse.com"),
            )

            # Configure Langfuse context with tracing status
            langfuse_context.configure(
                secret_key=credentials["secret_key"],
                public_key=credentials["public_key"],
                host=credentials.get("host", "https://cloud.langfuse.com"),
                enabled=enabled,
            )

            return langfuse, True

        else:
            # If no credentials, disable tracing
            # Disable Langfuse context if no credentials are provided
            langfuse_context.configure(
                secret_key=None,
                public_key=None,
                host=None,
                enabled=False,
            )

            return None, False

    except Exception as e:
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
        warnings.warn(f"Failed to configure OpenAI client: {str(e)}")
        return None, False
