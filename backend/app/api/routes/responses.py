import logging

import openai
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.api.deps import get_db, get_current_user_org_project
from app.api.routes.threads import send_callback
from app.core.db import engine
from app.core.langfuse.langfuse import LangfuseTracer
from app.crud.assistants import get_assistant_by_id
from app.crud.credentials import get_provider_credential
from app.crud.openai_conversation import (
    create_conversation,
    get_ancestor_id_from_response,
    get_conversation_by_ancestor_id,
)
from app.models import (
    CallbackResponse,
    Diagnostics,
    FileResultChunk,
    ResponsesAPIRequest,
    ResponsesSyncAPIRequest,
    UserProjectOrg,
    OpenAIConversationCreate,
)
from app.utils import APIResponse, get_openai_client, mask_string


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


def send_response_callback(
    callback_url: str,
    callback_response: APIResponse,
    request_dict: dict,
) -> None:
    """Send a standardized callback response to the provided callback URL."""

    callback_data = callback_response.model_dump()

    send_callback(
        callback_url,
        {
            "success": callback_data.get("success", False),
            "data": {
                **(callback_data.get("data") or {}),
                **get_additional_data(request_dict),
            },
            "error": callback_data.get("error"),
            "metadata": None,
        },
    )


def process_response(
    request_data: dict,
    project_id: int,
    organization_id: int,
):
    """Process a response and send callback with results, with Langfuse tracing."""
    request = ResponsesAPIRequest(**request_data)
    assistant_id = request.assistant_id
    request_dict = request.model_dump()

    logger.info(
        f"[process_response] Starting generating response for assistant_id={mask_string(assistant_id)}, project_id={project_id}"
    )

    callback_response: APIResponse | None = None
    tracer: LangfuseTracer | None = None

    try:
        with Session(engine) as session:
            assistant = get_assistant_by_id(session, assistant_id, project_id)
            if not assistant:
                msg = f"Assistant not found: assistant_id={mask_string(assistant_id)}, project_id={project_id}"
                logger.error(f"[process_response] {msg}")
                callback_response = APIResponse.failure_response(error="Assistant not found or not active")
                return

            try:
                client = get_openai_client(session, organization_id, project_id)
            except HTTPException as e:
                callback_response = APIResponse.failure_response(error=str(e.detail))
                return

            langfuse_credentials = get_provider_credential(
                session=session,
                org_id=organization_id,
                provider="langfuse",
                project_id=project_id,
            )

            # Handle ancestor_id
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

        # --- Langfuse trace ---
        tracer = LangfuseTracer(
            credentials=langfuse_credentials,
            response_id=request.response_id,
        )
        tracer.start_trace(
            name="generate_response_async",
            input={"question": request.question, "assistant_id": assistant_id},
            metadata={"callback_url": request.callback_url},
            tags=[assistant_id],
        )

        tracer.start_generation(
            name="openai_response",
            input={"question": request.question},
            metadata={"model": assistant.model, "temperature": assistant.temperature},
        )

        # Build params
        params = {
            "model": assistant.model,
            "previous_response_id": ancestor_id,
            "instructions": assistant.instructions,
            "temperature": assistant.temperature,
            "input": [{"role": "user", "content": request.question}],
        }
        if assistant.vector_store_ids:
            params["tools"] = [{
                "type": "file_search",
                "vector_store_ids": assistant.vector_store_ids,
                "max_num_results": assistant.max_num_results,
            }]
            params["include"] = ["file_search_call.results"]

        # Generate response
        response = client.responses.create(**params)
        response_chunks = get_file_search_results(response)

        logger.info(
            f"[process_response] Successfully generated response: response_id={response.id}, assistant={mask_string(assistant_id)}, project_id={project_id}"
        )

        tracer.end_generation(
            output={"response_id": response.id, "message": response.output_text},
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
            output={"status": "success", "message": response.output_text, "error": None},
        )

        # Store conversation
        with Session(engine) as session:
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
            create_conversation(
                session=session,
                conversation=OpenAIConversationCreate(
                    response_id=response.id,
                    previous_response_id=response.previous_response_id,
                    ancestor_response_id=ancestor_response_id,
                    user_question=request.question,
                    response=response.output_text,
                    model=response.model,
                    assistant_id=assistant_id,
                ),
                project_id=project_id,
                organization_id=organization_id,
            )

        # Success callback payload
        callback_response = APIResponse.success_response(
            data=CallbackResponse(
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
            f"[process_response] OpenAI API error: {error_message}, project_id={project_id}",
            exc_info=True,
        )
        if tracer:
            tracer.log_error(error_message, response_id=request.response_id)
        callback_response = APIResponse.failure_response(error=error_message)

    finally:
        if tracer:
            tracer.flush()
        if request.callback_url and callback_response:
            send_response_callback(request.callback_url, callback_response, request_dict)

    return callback_response



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

    request_dict = request.model_dump()
    background_tasks.add_task(
        process_response,
        request_dict,
        project_id,
        organization_id,
    )

    logger.info(
        f"[response] Background task scheduled for response processing: assistant_id={mask_string(request.assistant_id)}, project_id={project_id}, organization_id={organization_id}"
    )
    additional_data = get_additional_data(request_dict)

    return {
        "success": True,
        "data": {
            "status": "processing",
            "message": "Response creation started",
            **additional_data,
        },
        "error": None,
        "metadata": None,
    }


@router.post("/responses/sync", response_model=APIResponse[CallbackResponse])
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

    try:
        client = get_openai_client(_session, organization_id, project_id)
    except HTTPException as e:
        request_dict = request.model_dump()
        additional_data = get_additional_data(request_dict)
        return JSONResponse(
            status_code=e.status_code,
            content={
                "success": False,
                "data": additional_data if additional_data else None,
                "error": str(e.detail),
                "metadata": None,
            }
        )

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

        request_dict = request.model_dump()
        additional_data = get_additional_data(request_dict)

        return APIResponse.success_response(
            data=CallbackResponse(
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
                **additional_data,
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
        # Create a custom error response with additional data in data field
        additional_data = get_additional_data(request_dict)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "data": additional_data if additional_data else None,
                "error": error_message,
                "metadata": None,
            }
        )
