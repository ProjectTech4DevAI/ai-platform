from fastapi import Request
import logging

logger = logging.getLogger(__name__)


async def auth_middleware(request: Request) -> bool:
    """Authenticates the incoming request"""
    logger.info("Inside auth middleware")

    # TODO: authenticate the incoming request based on headers etc.

    # TODO: set the current org & client in the request state
    request.state.foo = "bar"

    return True
