from typing import Optional
import time

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
