import logging
import openai
from fastapi import HTTPException
from sqlmodel import Session
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
	OpenAIConversationCreate,
)
from app.utils import APIResponse, get_openai_client, handle_openai_error, mask_string

logger = logging.getLogger(__name__)


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


def process_response_task(request_data: dict, project_id: int, organization_id: int):
	"""Process a response and return callback payload, for Celery use."""
	request = ResponsesAPIRequest(**request_data)
	assistant_id = request.assistant_id
	request_dict = request.model_dump()

	logger.info(
		f"[process_response_task] Generating response for assistant_id={mask_string(assistant_id)}, project_id={project_id}"
	)

	callback_response: APIResponse | None = None
	tracer: LangfuseTracer | None = None

	try:
		with Session(engine) as session:
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
