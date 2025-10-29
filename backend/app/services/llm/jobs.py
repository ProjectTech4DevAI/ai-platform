import logging
from uuid import UUID

from asgi_correlation_id import correlation_id
from fastapi import HTTPException
from sqlmodel import Session

from app.core.db import engine
from app.crud.jobs import JobCrud
from app.models import JobStatus, JobType, JobUpdate, LLMCallRequest, LLMCallResponse
from app.utils import APIResponse, send_callback
from app.celery.utils import start_high_priority_job
from app.services.llm.providers.registry import get_llm_provider


logger = logging.getLogger(__name__)


def start_job(
    db: Session, request: LLMCallRequest, project_id: int, organization_id: int
) -> UUID:
    """Create an LLM job and schedule Celery task."""
    trace_id = correlation_id.get() or "N/A"
    job_crud = JobCrud(session=db)
    job = job_crud.create(job_type=JobType.LLM_API, trace_id=trace_id)

    try:
        task_id = start_high_priority_job(
            function_path="app.services.llm.jobs.execute_job",
            project_id=project_id,
            job_id=str(job.id),
            trace_id=trace_id,
            request_data=request.model_dump(),
            organization_id=organization_id,
        )
    except Exception as e:
        logger.error(
            f"[start_job] Error starting Celery task: {str(e)} | job_id={job.id}, project_id={project_id}",
            exc_info=True,
        )
        job_update = JobUpdate(status=JobStatus.FAILED, error_message=str(e))
        job_crud.update(job_id=job.id, job_update=job_update)
        raise HTTPException(
            status_code=500, detail="Internal server error while executing LLM call"
        )

    logger.info(
        f"[start_job] Job scheduled for LLM call | job_id={job.id}, project_id={project_id}, task_id={task_id}"
    )
    return job.id


def handle_job_error(
    job_id: UUID,
    callback_url: str | None,
    callback_response: APIResponse,
) -> dict:
    """Handle job failure uniformly — send callback and update DB."""
    with Session(engine) as session:
        job_crud = JobCrud(session=session)

        if callback_url:
            send_callback(
                callback_url=callback_url,
                data=callback_response.model_dump(),
            )

        job_crud.update(
            job_id=job_id,
            job_update=JobUpdate(
                status=JobStatus.FAILED,
                error_message=callback_response.error,
            ),
        )

    return callback_response.model_dump()


def execute_job(
    request_data: dict,
    project_id: int,
    organization_id: int,
    job_id: str,
    task_id: str,
    task_instance,
) -> dict:
    """Celery task to process an LLM request asynchronously.

    Returns:
        dict: Serialized APIResponse[LLMCallResponse] on success, APIResponse[None] on failure
    """

    request = LLMCallRequest(**request_data)
    job_id: UUID = UUID(job_id)

    config = request.config
    provider = config.completion.provider

    logger.info(
        f"[execute_job] Starting LLM job execution | job_id={job_id}, task_id={task_id}, "
        f"provider={provider}"
    )

    try:
        # Update job status to PROCESSING
        with Session(engine) as session:
            job_crud = JobCrud(session=session)
            job_crud.update(
                job_id=job_id, job_update=JobUpdate(status=JobStatus.PROCESSING)
            )

            provider_instance = get_llm_provider(
                session=session,
                provider_type=provider,
                project_id=project_id,
                organization_id=organization_id,
            )

        response, error = provider_instance.execute(
            completion_config=config.completion,
            query=request.query,
            include_provider_raw_response=request.include_provider_raw_response,
        )

        if response:
            callback = APIResponse.success_response(
                data=response, metadata=request.request_metadata
            )
            if request.callback_url:
                send_callback(
                    callback_url=request.callback_url,
                    data=callback.model_dump(),
                )

            with Session(engine) as session:
                job_crud = JobCrud(session=session)

                job_crud.update(
                    job_id=job_id, job_update=JobUpdate(status=JobStatus.SUCCESS)
                )
                logger.info(
                    f"[execute_job] Successfully completed LLM job | job_id={job_id}, "
                    f"provider_response_id={response.response.provider_response_id}, tokens={response.usage.total_tokens}"
                )
                return callback.model_dump()

        callback = APIResponse.failure_response(
            error=error or "Unknown error occurred",
            metadata=request.request_metadata,
        )
        return handle_job_error(job_id, request.callback_url, callback)

    except Exception as e:
        callback = APIResponse.failure_response(
            error=f"Unexpected error in LLM job execution: {str(e)}",
            metadata=request.request_metadata,
        )
        logger.error(
            f"[execute_job] {callback.error} | job_id={job_id}, task_id={task_id}",
            exc_info=True,
        )
        return handle_job_error(job_id, request.callback_url, callback)
