import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.exception_handlers import (
    register_exception_handlers,
    NotFoundException,
    BadRequestException,
    ForbiddenException,
    ServiceUnavailableException,
    DatabaseException,
    UnhandledAppException,
    OpenAIServiceException,
    CallbackFailedException,
)


@pytest.fixture
def app_with_exception_handlers():
    app = FastAPI()
    register_exception_handlers(app)

    # Add routes that trigger each exception
    @app.get("/raise/not_found")
    def raise_not_found():
        raise NotFoundException("Item not found")

    @app.get("/raise/bad_request")
    def raise_bad_request():
        raise BadRequestException("Invalid input")

    @app.get("/raise/forbidden")
    def raise_forbidden():
        raise ForbiddenException("Access denied")

    @app.get("/raise/service_unavailable")
    def raise_service_unavailable():
        raise ServiceUnavailableException("Service temporarily down")

    @app.get("/raise/database")
    def raise_database():
        raise DatabaseException("Integrity error")

    @app.get("/raise/openai")
    def raise_openai():
        raise OpenAIServiceException("OpenAI model failed")

    @app.get("/raise/callback")
    def raise_callback():
        raise CallbackFailedException("Webhook timeout")

    return app


@pytest.mark.parametrize(
    "path,status,message_substring",
    [
        ("/raise/not_found", 404, "Item not found"),
        ("/raise/bad_request", 400, "Invalid input"),
        ("/raise/forbidden", 403, "Access denied"),
        ("/raise/service_unavailable", 503, "temporarily down"),
        ("/raise/database", 403, "Integrity error"),
        ("/raise/openai", 502, "OpenAI model failed"),
        ("/raise/callback", 500, "Callback delivery failed"),
    ],
)
def test_custom_exceptions(
    app_with_exception_handlers, path, status, message_substring
):
    client = TestClient(app_with_exception_handlers)
    response = client.get(path)
    json_data = response.json()

    assert response.status_code == status
    assert json_data["success"] is False
    assert "error" in json_data
    assert message_substring in json_data["error"]
