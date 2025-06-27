from typing import Optional, Dict, Any
import logging

import openai
from pydantic import BaseModel, Extra
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from openai import OpenAI
from sqlmodel import Session

from app.api.deps import get_current_user_org, get_db
from app.crud.credentials import get_provider_credential
from app.crud.assistants import get_assistant_by_id
from app.models import UserOrganization
from app.utils import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["responses"])


def handle_openai_error(e: openai.OpenAIError) -> str:
    """Extract error message from OpenAI error."""
    if isinstance(e.body, dict) and "message" in e.body:
        return e.body["message"]
    return str(e)


class ResponsesAPIRequest(BaseModel):
    project_id: int
    assistant_id: str
    question: str
    callback_url: Optional[str] = None
    response_id: Optional[str] = None

    class Config:
        extra = Extra.allow


class ResponsesSyncAPIRequest(BaseModel):
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

    class Config:
        extra = (
            Extra.allow
        )  # This allows additional fields to be included in the response


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


def get_additional_data(request: dict) -> dict:
    """Extract additional data from request, excluding specific keys."""
    return {
        k: v
        for k, v in request.items()
        if k
        not in {"project_id", "assistant_id", "callback_url", "response_id", "question"}
    }


def process_response(
    request: ResponsesAPIRequest, client: OpenAI, assistant, organization_id: int
):
    """Process a response and send callback with results."""
    logger.info(
        f"Starting generating response for assistant_id={request.assistant_id}, project_id={request.project_id}, organization_id={organization_id}"
    )
    try:
        # Create response with or without tools based on vector_store_id
        params = {
            "model": assistant.model,
            "previous_response_id": request.response_id,
            "instructions": assistant.instructions,
            "temperature": assistant.temperature,
            "input": [{"role": "user", "content": request.question}],
        }

        if assistant.vector_store_id:
            params["tools"] = [
                {
                    "type": "file_search",
                    "vector_store_ids": [assistant.vector_store_id],
                    "max_num_results": assistant.max_num_results,
                }
            ]
            params["include"] = ["file_search_call.results"]

        response = client.responses.create(**params)

        response_chunks = get_file_search_results(response)
        logger.info(
            f"Successfully generated response: response_id={response.id}, assistant={request.assistant_id}, project_id={request.project_id}, organization_id={organization_id}"
        )

        # Convert request to dict and include all fields
        request_dict = request.model_dump()
        callback_response = ResponsesAPIResponse.success_response(
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
                **{
                    k: v
                    for k, v in request_dict.items()
                    if k
                    not in {
                        "project_id",
                        "assistant_id",
                        "callback_url",
                        "response_id",
                        "question",
                    }
                },
            ),
        )
    except openai.OpenAIError as e:
        error_message = handle_openai_error(e)
        logger.error(
            f"OpenAI API error during response processing: {error_message}, project_id={request.project_id}, organization_id={organization_id}",
            exc_info=True,
        )
        callback_response = ResponsesAPIResponse.failure_response(error=error_message)

    if request.callback_url:
        logger.info(
            f"Sending callback to URL: {request.callback_url}, assistant={request.assistant_id}, project_id={request.project_id}, organization_id={organization_id}"
        )
        from app.api.routes.threads import send_callback

        send_callback(request.callback_url, callback_response.model_dump())
        logger.info(
            f"Callback sent successfully, assistant={request.assistant_id}, project_id={request.project_id}, organization_id={organization_id}"
        )


@router.post("/responses", response_model=dict)
async def responses(
    request: ResponsesAPIRequest,
    background_tasks: BackgroundTasks,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """Asynchronous endpoint that processes requests in background."""
    logger.info(
        f"Processing response request for assistant_id={request.assistant_id}, project_id={request.project_id}, organization_id={_current_user.organization_id}"
    )

    # Get assistant details
    assistant = get_assistant_by_id(
        _session, request.assistant_id, _current_user.organization_id
    )
    if not assistant:
        logger.error(
            f"Assistant not found: assistant_id={request.assistant_id}, project_id={request.project_id}, organization_id={_current_user.organization_id}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=404,
            detail="Assistant not found or not active",
        )

    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request.project_id,
    )
    if not credentials or "api_key" not in credentials:
        logger.error(
            f"OpenAI API key not configured for org_id={_current_user.organization_id}, project_id={request.project_id}, organization_id={_current_user.organization_id}",
            exc_info=True,
        )
        return {
            "success": False,
            "error": "OpenAI API key not configured for this organization.",
            "data": None,
            "metadata": None,
        }

    client = OpenAI(api_key=credentials["api_key"])

    # Send immediate response
    initial_response = {
        "success": True,
        "data": {
            "status": "processing",
            "message": "Response creation started",
            "success": True,
        },
        "error": None,
        "metadata": None,
    }

    # Schedule background task
    background_tasks.add_task(
        process_response, request, client, assistant, _current_user.organization_id
    )
    logger.info(
        f"Background task scheduled for response processing: assistant_id={request.assistant_id}, project_id={request.project_id}, organization_id={_current_user.organization_id}"
    )

    return initial_response


@router.post("/responses/sync", response_model=ResponsesAPIResponse)
async def responses_sync(
    request: ResponsesSyncAPIRequest,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org),
):
    """
    Synchronous endpoint for benchmarking OpenAI responses API
    """
    credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="openai",
        project_id=request.project_id,
    )
    if not credentials or "api_key" not in credentials:
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization."
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
        return Exception(error=handle_openai_error(e))
