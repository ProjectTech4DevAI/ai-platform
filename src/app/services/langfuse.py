from typing import Optional
import httpx
from httpx import HTTPStatusError

from ..schemas.langfuse.prompt import PromptMetaListResponse, PromptQueryParams, PromptDetailResponse, PromptCreateRequest
from ..core.config import settings

class LangfuseClient:
    def __init__(self):
        self.base_url = settings.LANGFUSE_HOST
        self.public_key = settings.LANGFUSE_PUBLIC_KEY
        self.secret_key = settings.LANGFUSE_SECRET_KEY

    async def create_prompt_version(self, prompt_data: PromptCreateRequest) -> PromptDetailResponse:
        """Create a new version of an existing prompt."""
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/public/v2/prompts",
                json=prompt_data.model_dump(by_alias=True, exclude_none=True),
                auth=(self.public_key, self.secret_key),
            )
            response.raise_for_status()
            data = response.json()
        
            return PromptDetailResponse.model_validate(data)

    async def get_prompts(self, query_params: PromptQueryParams) -> PromptMetaListResponse:
        """Fetch a list of prompt names with versions and labels."""
        params = query_params.model_dump(exclude_none=True)  # Auto-filter None values

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/public/v2/prompts",
                params=params,
                auth=(self.public_key, self.secret_key),
            )
            response.raise_for_status()
            return PromptMetaListResponse.model_validate(response.json())
        
    async def get_prompt(self, prompt_name: str, version: Optional[int] = None, label: Optional[str] = None) -> PromptDetailResponse:
        """Fetch a specific prompt by name, with optional version or label."""
        params = {}
        if version is not None:
            params["version"] = version
        if label is not None:
            params["label"] = label

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/public/v2/prompts/{prompt_name}",
                    params=params,
                    auth=(self.public_key, self.secret_key),
                )
                response.raise_for_status()
                return PromptDetailResponse.model_validate(response.json())
            except HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise