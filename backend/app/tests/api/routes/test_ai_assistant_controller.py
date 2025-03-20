import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.core.ai_assistant import AIAssistant

client = TestClient(app)

# Test data
test_assistant_data = {
    "name": "Test Assistant",
    "instructions": "Test instructions",
    "model": "gpt-4-turbo-preview"
}

test_message_data = {
    "content": "Hello, assistant!"
}

test_assistant_response = {
    "assistant_id": "asst_123",
    "name": "Test Assistant",
    "model": "gpt-4-turbo-preview",
    "created_at": 1234567890
}

test_thread_response = {
    "thread_id": "thread_123"
}

test_message_response = {
    "message_id": "msg_123"
}

test_run_response = {
    "response": "Hello! How can I help you?",
    "run_id": "run_123"
}

@pytest.fixture
def mock_ai_assistant():
    with patch('app.api.routes.ai_assistant_controller.AIAssistant') as mock:
        instance = mock.return_value
        instance.create_assistant = AsyncMock()
        instance.create_thread = AsyncMock()
        instance.add_message = AsyncMock()
        instance.run_assistant = AsyncMock()
        yield instance

class TestCreateAssistant:
    @pytest.mark.asyncio
    async def test_create_assistant_success(self, mock_ai_assistant):
        # Setup mock
        mock_ai_assistant.create_assistant.return_value = test_assistant_response

        # Make request
        response = client.post("/ai-assistant/create-assistant", json=test_assistant_data)

        # Assert response
        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "data": test_assistant_response,
            "error": None
        }
        mock_ai_assistant.create_assistant.assert_called_once_with(
            name=test_assistant_data["name"],
            instructions=test_assistant_data["instructions"],
            model=test_assistant_data["model"],
            tools=None
        )

    @pytest.mark.asyncio
    async def test_create_assistant_with_tools(self, mock_ai_assistant):
        # Test data with tools
        data_with_tools = {
            **test_assistant_data,
            "tools": [{"type": "code_interpreter"}]
        }
        mock_ai_assistant.create_assistant.return_value = test_assistant_response

        response = client.post("/ai-assistant/create-assistant", json=data_with_tools)

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_ai_assistant.create_assistant.assert_called_once_with(
            name=data_with_tools["name"],
            instructions=data_with_tools["instructions"],
            model=data_with_tools["model"],
            tools=data_with_tools["tools"]
        )

    @pytest.mark.asyncio
    async def test_create_assistant_failure(self, mock_ai_assistant):
        # Setup mock to raise exception
        mock_ai_assistant.create_assistant.side_effect = Exception("Creation failed")

        # Make request
        response = client.post("/ai-assistant/create-assistant", json=test_assistant_data)

        # Assert response
        assert response.status_code == 200
        assert response.json() == {
            "success": False,
            "data": None,
            "error": "Creation failed"
        }

class TestChatWithAssistant:
    @pytest.mark.asyncio
    async def test_chat_success(self, mock_ai_assistant):
        # Setup mocks
        mock_ai_assistant.create_thread.return_value = test_thread_response
        mock_ai_assistant.add_message.return_value = test_message_response
        mock_ai_assistant.run_assistant.return_value = test_run_response

        # Make request
        response = client.post(
            f"/ai-assistant/chat/asst_123",
            json=test_message_data
        )

        # Assert response
        assert response.status_code == 200
        assert response.json() == test_run_response

        # Verify all methods were called with correct arguments
        mock_ai_assistant.create_thread.assert_called_once()
        mock_ai_assistant.add_message.assert_called_once_with(
            "thread_123",
            test_message_data["content"]
        )
        mock_ai_assistant.run_assistant.assert_called_once_with(
            "asst_123",
            "thread_123"
        )

    @pytest.mark.asyncio
    async def test_chat_thread_creation_failure(self, mock_ai_assistant):
        # Setup mock to fail thread creation
        mock_ai_assistant.create_thread.return_value = {"error": "Thread creation failed"}

        # Make request
        response = client.post(
            f"/ai-assistant/chat/asst_123",
            json=test_message_data
        )

        # Assert response
        assert response.status_code == 400
        assert response.json() == {"detail": "Thread creation failed"}
        mock_ai_assistant.add_message.assert_not_called()
        mock_ai_assistant.run_assistant.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_message_addition_failure(self, mock_ai_assistant):
        # Setup mocks
        mock_ai_assistant.create_thread.return_value = test_thread_response
        mock_ai_assistant.add_message.return_value = {"error": "Message addition failed"}

        # Make request
        response = client.post(
            f"/ai-assistant/chat/asst_123",
            json=test_message_data
        )

        # Assert response
        assert response.status_code == 400
        assert response.json() == {"detail": "Message addition failed"}
        mock_ai_assistant.run_assistant.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_run_failure(self, mock_ai_assistant):
        # Setup mocks
        mock_ai_assistant.create_thread.return_value = test_thread_response
        mock_ai_assistant.add_message.return_value = test_message_response
        mock_ai_assistant.run_assistant.return_value = {"error": "Run failed"}

        # Make request
        response = client.post(
            f"/ai-assistant/chat/asst_123",
            json=test_message_data
        )

        # Assert response
        assert response.status_code == 400
        assert response.json() == {"detail": "Run failed"}

    @pytest.mark.asyncio
    async def test_invalid_request_body(self):
        # Make request with invalid body
        response = client.post(
            f"/ai-assistant/chat/asst_123",
            json={}
        )

        # Assert response
        assert response.status_code == 422 