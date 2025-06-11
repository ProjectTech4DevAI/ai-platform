from typing import Optional

import openai
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from openai import OpenAI
from sqlmodel import Session

from app.api.deps import get_current_user_org, get_db
from app.crud.credentials import get_provider_credential
from app.models import UserOrganization
from app.utils import APIResponse
from app.core import logging, settings
from app.core.exception_handlers import OpenAIServiceException, BadRequestException

router = APIRouter(tags=["responses"])


def handle_openai_error(e: openai.OpenAIError) -> str:
    """Extract error message from OpenAI error."""
    if isinstance(e.body, dict) and "message" in e.body:
        return e.body["message"]
    return str(e)


class ResponsesAPIRequest(BaseModel):
    project_id: int

    model: str
    instructions: str
    vector_store_ids: list[str]
    max_num_results: Optional[int] = 20
    temperature: Optional[float] = 0.1
    response_id: Optional[str] = None

    question: str


class Diagnostics(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int

    model: str


class FileResultChunk(BaseModel):
    score: float
    text: str


class _APIResponse(BaseModel):
    status: str

    response_id: str
    message: str
    chunks: list[FileResultChunk]

    diagnostics: Optional[Diagnostics] = None


class ResponsesAPIResponse(APIResponse[_APIResponse]):
    pass


def get_file_search_results(response):
    results: list[FileResultChunk] = []

    for tool_call in response.output:
        if tool_call.type == "file_search_call":
            results.extend(
                [FileResultChunk(score=hit.score, text=hit.text) for hit in results]
            )

    return results


@router.post("/responses/sync", response_model=ResponsesAPIResponse)
async def responses_sync(
    request: ResponsesAPIRequest,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """
    Temp synchronous endpoint for benchmarking OpenAI responses API
    """
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request.project_id,
    )
    if not credentials or "api_key" not in credentials:
        raise BadRequestException(
            "OpenAI API key not configured for this organization."
        )

    client = OpenAI(api_key=credentials["api_key"])

    try:
        response = client.responses.create(
            model=request.model,
            previous_response_id=request.response_id,
            instructions=request.instructions,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": request.vector_store_ids,
                    "max_num_results": request.max_num_results,
                }
            ],
            temperature=request.temperature,
            input=[{"role": "user", "content": request.question}],
            include=["file_search_call.results"],
        )

        response_chunks = get_file_search_results(response)

        return ResponsesAPIResponse.success_response(
            data=_APIResponse(
                status="success",
                response_id=response.id,
                message=response.output_text,
                chunks=response_chunks,
                diagnostics=Diagnostics(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.total_tokens,
                    model=response.model,
                ),
            ),
        )
    except openai.OpenAIError as e:
        raise OpenAIServiceException(handle_openai_error(e))
