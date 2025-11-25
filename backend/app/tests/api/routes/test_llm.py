from unittest.mock import patch
from fastapi.testclient import TestClient
from app.models import LLMCallRequest
from app.models.llm.request import (
    QueryParams,
    LLMCallConfig,
    CompletionConfig,
    ConfigBlob,
)


def test_llm_call_success(client: TestClient, user_api_key_header: dict[str, str]):
    """Test successful LLM call with mocked start_high_priority_job."""
    with patch("app.services.llm.jobs.start_high_priority_job") as mock_start_job:
        mock_start_job.return_value = "test-task-id"

        payload = LLMCallRequest(
            query=QueryParams(input="What is the capital of France?"),
            config=LLMCallConfig(
                blob=ConfigBlob(
                    completion=CompletionConfig(
                        provider="openai",
                        params={
                            "model": "gpt-4",
                            "temperature": 0.7,
                        },
                    )
                )
            ),
            callback_url="https://example.com/callback",
        )

        response = client.post(
            "api/v1/llm/call",
            json=payload.model_dump(mode="json"),
            headers=user_api_key_header,
        )

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["success"] is True
        assert "response is being generated" in response_data["data"]["message"]

        mock_start_job.assert_called_once()
