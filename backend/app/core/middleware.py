import logging
import time
from fastapi import Request, Response

logger = logging.getLogger("http_request_logger")


async def http_request_logger(request: Request, call_next) -> Response:
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception("Unhandled exception during request")
        raise

    process_time = (time.time() - start_time) * 1000  # ms
    client_ip = request.client.host if request.client else "unknown"

    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} [{process_time:.2f}ms]"
    )
    return response
