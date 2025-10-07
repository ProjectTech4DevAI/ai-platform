import sentry_sdk

from fastapi import FastAPI
from fastapi.routing import APIRoute
from asgi_correlation_id.middleware import CorrelationIdMiddleware
from app.api.main import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import http_request_logger

from app.load_env import load_environment

# Load environment variables
load_environment()


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.middleware("http")(http_request_logger)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)

register_exception_handlers(app)
