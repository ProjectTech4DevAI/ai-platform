import logging
from uuid import UUID
import openai
from fastapi import HTTPException
from sqlmodel import Session
from app.core.db import engine
from app.core.langfuse.langfuse import LangfuseTracer
from app.crud import (
	JobCrud,
	get_assistant_by_id,
	get_provider_credential,
	create_conversation,
	get_ancestor_id_from_response,
	get_conversation_by_ancestor_id,

)
from app.models import (
	CallbackResponse,
	Diagnostics,
	FileResultChunk,
	JobType,
	JobStatus,
	JobUpdate,
	ResponsesAPIRequest,
	OpenAIConversationCreate,
)
from app.utils import APIResponse, get_openai_client, handle_openai_error, mask_string
from app.celery.utils import start_high_priority_job
from app.api.routes.threads import send_callback

logger = logging.getLogger(__name__)


def start_job(
    db: Session,
    request: ResponsesAPIRequest,
    project_id: int,
    organization_id: int,
) -> UUID:
    """Create a response job and schedule Celery task."""

    job_crud = JobCrud(session=db)
    job = job_crud.create(job_type=JobType.RESPONSE, trace_id="Aviraj")

    # Schedule the Celery task
    task_id = start_high_priority_job(
        function_path="app.services.response.execute_job",
        project_id=project_id,
        job_id=str(job.id),
        request_data=request.model_dump(),
        organization_id=organization_id,
    )

    logger.info(
        f"[start_job] Job scheduled to generate response  | job_id={job.id}, project_id={project_id}, task_id={task_id}"
    )
    return job.id


def get_file_search_results(response):
	results: list[FileResultChunk] = []
	for tool_call in response.output:
		if tool_call.type == "file_search_call":
			results.extend(
				[FileResultChunk(score=hit.score, text=hit.text) for hit in results]
			)
	return results


def get_additional_data(request: dict) -> dict:
	async_exclude_keys = {"assistant_id", "callback_url", "response_id", "question"}
	sync_exclude_keys = {
		"model",
		"instructions",
		"vector_store_ids",
		"max_num_results",
		"temperature",
		"response_id",
		"question",
	}
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

    # Convert Pydantic model to dict
    callback_response = callback_response.model_dump()

    send_callback(
        callback_url,
        {
            "success": callback_response.get("success", False),
            "data": {
                **(callback_response.get("data") or {}),
                **get_additional_data(request_dict),
            },
            "error": callback_response.get("error"),
            "metadata": None,
        },
    )


def execute_job(
	request_data: dict,
	project_id: int,
	organization_id: int,
	job_id: str,
	task_id: str,
	task_instance,
) -> APIResponse | None:
	"""Celery task to process a response request asynchronously."""
	request_data = ResponsesAPIRequest(**request_data)
	job_id = UUID(job_id)
	response = process_response(
		request=request_data,
		project_id=project_id,
		organization_id=organization_id,
		job_id=job_id,
		task_id=task_id,
		task_instance=task_instance,
	)
	if response is None:
		response = APIResponse.failure_response(error="Unknown error occurred")

	with Session(engine) as session:
		job_crud = JobCrud(session=session)
		if response.success:
			job_update = JobUpdate(status=JobStatus.SUCCESS)
		else:
			job_update = JobUpdate(status=JobStatus.FAILED, error_message=response.error)
		job_crud.update(job_id=job_id, job_update=job_update)


	if request_data.callback_url:
		send_response_callback(
			callback_url=request_data.callback_url,
			callback_response=response,
			request_dict=request_data.model_dump(),
		)

	return response.model_dump()


def process_response(
	request: ResponsesAPIRequest,
    project_id: int,
    organization_id: int,
	job_id: UUID,
    task_id: str,
    task_instance,
)-> APIResponse:
	"""Process a response and return callback payload, for Celery use."""
	assistant_id = request.assistant_id

	logger.info(
		f"[process_response_task] Generating response for assistant_id={mask_string(assistant_id)}, project_id={project_id}"
	)

	callback_response: APIResponse | None = None
	tracer: LangfuseTracer | None = None

	try:
		with Session(engine) as session:
			job_crud = JobCrud(session=session)

			job_update = JobUpdate(status=JobStatus.PROCESSING, task_id=UUID(task_id))
			job_crud.update(job_id=job_id, job_update=job_update)
			
			assistant = get_assistant_by_id(session, assistant_id, project_id)
			if not assistant:
				msg = f"Assistant not found: assistant_id={mask_string(assistant_id)}, project_id={project_id}"
				logger.error(f"[process_response_task] {msg}")
				callback_response = APIResponse.failure_response(error="Assistant not found or not active")
				return callback_response

			try:
				client = get_openai_client(session, organization_id, project_id)
			except HTTPException as e:
				callback_response = APIResponse.failure_response(error=str(e.detail))
				return callback_response

			langfuse_credentials = get_provider_credential(
				session=session,
				org_id=organization_id,
				provider="langfuse",
				project_id=project_id,
			)

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

		response = client.responses.create(**params)
		response_chunks = get_file_search_results(response)

		logger.info(
			f"[process_response_task] Successfully generated response: response_id={response.id}, assistant={mask_string(assistant_id)}, project_id={project_id}"
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
			job_crud = JobCrud(session=session)
			job_update = JobUpdate(status=JobStatus.SUCCESS)
			job_crud.update(job_id=job_id, job_update=job_update)

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
			f"[process_response_task] OpenAI API error: {error_message}, project_id={project_id}",
			exc_info=True,
		)
		if tracer:
			tracer.log_error(error_message, response_id=request.response_id)
		
		callback_response = APIResponse.failure_response(error=error_message)

	finally:
		if tracer:
			tracer.flush()

	return callback_response
