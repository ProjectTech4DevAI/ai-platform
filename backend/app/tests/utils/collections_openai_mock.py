from unittest.mock import MagicMock


def get_mock_openai_client():
    mock_client = MagicMock()

    # Vector store
    mock_vector_store = MagicMock()
    mock_vector_store.id = "mock_vector_store_id"
    mock_client.vector_stores.create.return_value = mock_vector_store

    # File upload + polling
    mock_file_batch = MagicMock()
    mock_file_batch.file_counts.completed = 2
    mock_file_batch.file_counts.total = 2
    mock_client.vector_stores.file_batches.upload_and_poll.return_value = (
        mock_file_batch
    )

    # File list
    mock_client.vector_stores.files.list.return_value = {"data": []}

    # Assistant
    mock_assistant = MagicMock()
    mock_assistant.id = "mock_assistant_id"
    mock_assistant.name = "Mock Assistant"
    mock_assistant.model = "gpt-4o"
    mock_assistant.instructions = "Mock instructions"
    mock_client.beta.assistants.create.return_value = mock_assistant

    return mock_client
