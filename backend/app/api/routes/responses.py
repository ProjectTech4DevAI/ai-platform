import logging
from typing import Optional

import openai
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Extra
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.api.routes.threads import send_callback
from app.crud.assistants import get_assistant_by_id
from app.crud.credentials import get_provider_credential
from app.crud.openai_conversation import (
    create_conversation,
    get_ancestor_id_from_response,
    get_conversation_by_ancestor_id,
)
from app.models import UserProjectOrg, OpenAIConversationCreate
from app.utils import APIResponse, mask_string
from app.core.langfuse.langfuse import LangfuseTracer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["responses"])


def handle_openai_error(e: openai.OpenAIError) -> str:
    """Extract error message from OpenAI error."""
    # Try to get error message from different possible attributes
    if hasattr(e, "body") and isinstance(e.body, dict) and "message" in e.body:
        return e.body["message"]
    elif hasattr(e, "message"):
        return e.message
    elif hasattr(e, "response") and hasattr(e.response, "json"):
        try:
            error_data = e.response.json()
            if isinstance(error_data, dict) and "error" in error_data:
                error_info = error_data["error"]
                if isinstance(error_info, dict) and "message" in error_info:
                    return error_info["message"]
        except:
            pass
    return str(e)


class ResponsesAPIRequest(BaseModel):
    assistant_id: str
    question: str
    callback_url: Optional[str] = None
    response_id: Optional[str] = None

    class Config:
        extra = Extra.allow


class ResponsesSyncAPIRequest(BaseModel):
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
        extra = Extra.allow


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
    # Keys to exclude for async request (ResponsesAPIRequest)
    async_exclude_keys = {"assistant_id", "callback_url", "response_id", "question"}
    # Keys to exclude for sync request (ResponsesSyncAPIRequest)
    sync_exclude_keys = {
        "model",
        "instructions",
        "vector_store_ids",
        "max_num_results",
        "temperature",
        "response_id",
        "question",
    }

    # Determine which keys to exclude based on the request structure
    if "assistant_id" in request:
        exclude_keys = async_exclude_keys
    else:
        exclude_keys = sync_exclude_keys

    return {k: v for k, v in request.items() if k not in exclude_keys}


def process_response(
    request: ResponsesAPIRequest,
    client: OpenAI,
    assistant,
    tracer: LangfuseTracer,
    project_id: int,
    organization_id: int,
    session: Session,
):
    """Process a response and send callback with results, with Langfuse tracing."""
    logger.info(
        f"[process_response] Starting generating response for assistant_id={mask_string(request.assistant_id)}, project_id={project_id}"
    )

    tracer.start_trace(
        name="generate_response_async",
        input={"question": request.question, "assistant_id": request.assistant_id},
        metadata={"callback_url": request.callback_url},
    )

    tracer.start_generation(
        name="openai_response",
        input={"question": request.question},
        metadata={"model": assistant.model, "temperature": assistant.temperature},
    )

    try:
        # Get the latest conversation by ancestor ID to use as previous_response_id
        ancestor_id = request.response_id
        latest_conversation = None
        if ancestor_id:
            latest_conversation = get_conversation_by_ancestor_id(
                session=session,
                ancestor_response_id=ancestor_id,
                project_id=project_id,
            )
            if latest_conversation:
                ancestor_id = latest_conversation.response_id

        params = {
            "model": assistant.model,
            "previous_response_id": ancestor_id,
            "instructions": assistant.instructions,
            "temperature": assistant.temperature,
            "input": [{"role": "user", "content": request.question}],
        }

        if assistant.vector_store_ids:
            params["tools"] = [
                {
                    "type": "file_search",
                    "vector_store_ids": assistant.vector_store_ids,
                    "max_num_results": assistant.max_num_results,
                }
            ]
            params["include"] = ["file_search_call.results"]

        response = client.responses.create(**params)

        response_chunks = get_file_search_results(response)

        logger.info(
            f"[process_response] Successfully generated response: response_id={response.id}, assistant={mask_string(request.assistant_id)}, project_id={project_id}"
        )

        tracer.end_generation(
            output={
                "response_id": response.id,
                "message": response.output_text,
            },
            usage={
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "total": response.usage.total_tokens,
                "unit": "TOKENS",
            },
            model=response.model,
        )

        tracer.update_trace(
            tags=[response.id],
            output={
                "status": "success",
                "message": response.output_text,
                "error": None,
            },
        )
        # Set ancestor_response_id using CRUD function
        ancestor_response_id = (
            latest_conversation.ancestor_response_id
            if latest_conversation
            else get_ancestor_id_from_response(
                session=session,
                current_response_id=response.id,
                previous_response_id=response.previous_response_id,
                project_id=project_id,
            )
        )

        # Create conversation record in database
        conversation_data = OpenAIConversationCreate(
            response_id=response.id,
            previous_response_id=response.previous_response_id,
            ancestor_response_id=ancestor_response_id,
            user_question=request.question,
            response=response.output_text,
            model=response.model,
            assistant_id=request.assistant_id,
        )

        create_conversation(
            session=session,
            conversation=conversation_data,
            project_id=project_id,
            organization_id=organization_id,
        )

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
                **get_additional_data(request_dict),
            )
        )
    except openai.OpenAIError as e:
        error_message = handle_openai_error(e)
        logger.error(
            f"[process_response] OpenAI API error during response processing: {error_message}, project_id={project_id}",
            exc_info=True,
        )
        tracer.log_error(error_message, response_id=request.response_id)

        request_dict = request.model_dump()
    tracer.flush()

    if request.callback_url:
        logger.info(
            f"[process_response] Sending callback to URL: {request.callback_url}, assistant={mask_string(request.assistant_id)}, project_id={project_id}"
        )

        # Send callback with webhook-specific response format
        send_callback(
            request.callback_url,
            {
                "success": False,
                "data": get_additional_data(request_dict),
                "error": error_message,
                "metadata": None,
            },
        )
        logger.info(
            f"[process_response] Callback sent successfully, assistant={mask_string(request.assistant_id)}, project_id={project_id}"
        )


@router.post("/responses", response_model=dict)
async def responses(
    request: ResponsesAPIRequest,
    background_tasks: BackgroundTasks,
    _session: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Asynchronous endpoint that processes requests in background with Langfuse tracing."""

    project_id, organization_id = (
        _current_user.project_id,
        _current_user.organization_id,
    )

    assistant = get_assistant_by_id(_session, request.assistant_id, project_id)
    if not assistant:
        logger.warning(
            f"[response] Assistant not found: assistant_id={mask_string(request.assistant_id)}, project_id={project_id}, organization_id={organization_id}",
        )
        raise HTTPException(status_code=404, detail="Assistant not found or not active")

    credentials = get_provider_credential(
        session=_session,
        org_id=organization_id,
        provider="openai",
        project_id=project_id,
    )
    if not credentials or "api_key" not in credentials:
        logger.error(
            f"[response] OpenAI API key not configured for org_id={organization_id}, project_id={project_id}"
        )
        request_dict = request.model_dump()
        return {
            "success": False,
            "error": "OpenAI API key not configured for this organization.",
            "data": get_additional_data(request_dict),
            "metadata": None,
        }

    client = OpenAI(api_key=credentials["api_key"])

    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=organization_id,
        provider="langfuse",
        project_id=project_id,
    )
    tracer = LangfuseTracer(
        credentials=langfuse_credentials,
        response_id=request.response_id,
    )

    background_tasks.add_task(
        process_response,
        request,
        client,
        assistant,
        tracer,
        project_id,
        organization_id,
        _session,
    )

    logger.info(
        f"[response] Background task scheduled for response processing: assistant_id={mask_string(request.assistant_id)}, project_id={project_id}, organization_id={organization_id}"
    )

    return {
        "success": True,
        "data": {
            "status": "processing",
            "message": "Response creation started",
        },
        "error": None,
        "metadata": None,
    }


@router.post("/responses/sync", response_model=ResponsesAPIResponse)
async def responses_sync(
    request: ResponsesSyncAPIRequest,
    _session: Session = Depends(get_db),
    _current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """Synchronous endpoint for benchmarking OpenAI responses API with Langfuse tracing."""
    project_id, organization_id = (
        _current_user.project_id,
        _current_user.organization_id,
    )

    credentials = get_provider_credential(
        session=_session,
        org_id=organization_id,
        provider="openai",
        project_id=project_id,
    )
    if not credentials or "api_key" not in credentials:
        request_dict = request.model_dump()
        logger.error(
            f"[response_sync] OpenAI API key not configured for org_id={organization_id}, project_id={project_id}"
        )
        return APIResponse.failure_response(
            error="OpenAI API key not configured for this organization.",
            metadata=get_additional_data(request_dict),
        )

    client = OpenAI(api_key=credentials["api_key"])

    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=organization_id,
        provider="langfuse",
        project_id=project_id,
    )
    tracer = LangfuseTracer(
        credentials=langfuse_credentials,
        response_id=request.response_id,
    )

    tracer.start_trace(
        name="generate_response_sync", input={"question": request.question}
    )
    tracer.start_generation(
        name="openai_response",
        input={"question": request.question},
        metadata={"model": request.model, "temperature": request.temperature},
    )

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

        tracer.end_generation(
            output={
                "response_id": response.id,
                "message": response.output_text,
            },
            usage={
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "total": response.usage.total_tokens,
                "unit": "TOKENS",
            },
            model=response.model,
        )

        tracer.update_trace(
            tags=[response.id],
            output={
                "status": "success",
                "message": response.output_text,
                "error": None,
            },
        )

        tracer.flush()
        logger.info(
            f"[response_sync] Successfully generated response: response_id={response.id}, project_id={project_id}"
        )
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
            )
        )
    except openai.OpenAIError as e:
        error_message = handle_openai_error(e)
        logger.error(
            f"[response_sync] OpenAI API error during response processing: {error_message}, project_id={project_id}",
            exc_info=True,
        )
        tracer.log_error(error_message, response_id=request.response_id)
        tracer.flush()

        request_dict = request.model_dump()
        return ResponsesAPIResponse.failure_response(
            error=error_message, metadata=get_additional_data(request_dict)
        )
