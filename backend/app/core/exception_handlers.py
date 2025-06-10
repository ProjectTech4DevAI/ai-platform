from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.utils import APIResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
    HTTP_502_BAD_GATEWAY,
)


# Custom Exceptions
class NotFoundException(Exception):
    pass


class BadRequestException(Exception):
    pass


class ServiceUnavailableException(Exception):
    pass


class DatabaseException(Exception):
    pass


class UnhandledAppException(Exception):
    pass


class OpenAIServiceException(Exception):
    pass


class CallbackFailedException(Exception):
    pass


# Exception Handler Registration
def register_exception_handlers(app: FastAPI):
    @app.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException):
        return JSONResponse(
            status_code=HTTP_404_NOT_FOUND,
            content=APIResponse.failure_response(str(exc)).model_dump(),
        )

    @app.exception_handler(BadRequestException)
    async def bad_request_handler(request: Request, exc: BadRequestException):
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content=APIResponse.failure_response(str(exc)).model_dump(),
        )

    @app.exception_handler(ServiceUnavailableException)
    async def service_unavailable_handler(
        request: Request, exc: ServiceUnavailableException
    ):
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content=APIResponse.failure_response(str(exc)).model_dump(),
        )

    @app.exception_handler(DatabaseException)
    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(IntegrityError)
    async def database_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=HTTP_403_FORBIDDEN,
            content=APIResponse.failure_response(str(exc)).model_dump(),
        )

    @app.exception_handler(OpenAIServiceException)
    async def openai_service_error_handler(
        request: Request, exc: OpenAIServiceException
    ):
        return JSONResponse(
            status_code=HTTP_502_BAD_GATEWAY, content={"detail": str(exc)}
        )

    @app.exception_handler(CallbackFailedException)
    async def callback_failed_handler(request: Request, exc: CallbackFailedException):
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=APIResponse.failure_response(
                f"Callback delivery failed: {str(exc)}"
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content=APIResponse.failure_response("Validation error").model_dump()
            | {"detail": exc.errors()},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=APIResponse.failure_response(exc.detail).model_dump()
            | {"detail": exc.detail},
        )

    @app.exception_handler(UnhandledAppException)
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=APIResponse.failure_response(
                str(exc) or "An unexpected error occurred."
            ).model_dump(),
        )
