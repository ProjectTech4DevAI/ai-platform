from typing import Optional
import time

from unittest.mock import MagicMock
from openai.types.beta import Assistant as OpenAIAssistant
from openai.types.beta.assistant import ToolResources, ToolResourcesFileSearch
from openai.types.beta.assistant_tool import FileSearchTool
from openai.types.beta.file_search_tool import FileSearch


def mock_openai_assistant(
    assistant_id: str = "assistant_mock",
    vector_store_ids: Optional[list[str]] = ["vs_1", "vs_2"],
    max_num_results: int = 30,
) -> OpenAIAssistant:
    return OpenAIAssistant(
        id=assistant_id,
        created_at=int(time.time()),
        description="Mock description",
        instructions="Mock instructions",
        metadata={},
        model="gpt-4o",
        name="Mock Assistant",
        object="assistant",
        tools=[
            FileSearchTool(
                type="file_search",
                file_search=FileSearch(
                    max_num_results=max_num_results,
                ),
            )
        ],
        temperature=1.0,
        tool_resources=ToolResources(
            code_interpreter=None,
            file_search=ToolResourcesFileSearch(vector_store_ids=vector_store_ids),
        ),
        top_p=1.0,
        reasoning_effort=None,
    )


def get_mock_openai_client_with_vector_store():
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
