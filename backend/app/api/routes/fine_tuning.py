from typing import Optional
import logging
import time
from uuid import UUID

import openai
from openai import OpenAI
from sqlmodel import Session
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.models import (
    FineTuningJobCreate,
    FineTuningJobPublic,
    FineTuningUpdate,
    FineTuningStatus,
)
from app.core.cloud import AmazonCloudStorage
from app.crud.document import DocumentCrud
from app.utils import get_openai_client, APIResponse, mask_string, load_description
from app.crud import (
    create_fine_tuning_job,
    fetch_by_id,
    update_finetune_job,
    fetch_by_document_id,
)
from app.api.deps import CurrentUserOrgProject, SessionDep
from app.core.finetune.preprocessing import DataPreprocessor


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fine_tuning", tags=["fine_tuning"])


OPENAI_TO_INTERNAL_STATUS = {
    "validating_files": FineTuningStatus.running,
    "queued": FineTuningStatus.running,
    "running": FineTuningStatus.running,
    "succeeded": FineTuningStatus.completed,
    "failed": FineTuningStatus.failed,
}


def handle_openai_error(e: openai.OpenAIError) -> str:
    """Extract error message from OpenAI error."""
    if isinstance(e.body, dict) and "message" in e.body:
        return e.body["message"]
    return str(e)


def process_fine_tuning_job(
    job_id: int,
    ratio: float,
    session: Session,
    current_user: CurrentUserOrgProject,
    request: FineTuningJobCreate,
    client: OpenAI,
):
    start_time = time.time()
    project_id = current_user.project_id
    fine_tune = None

    logger.info(
        f"[process_fine_tuning_job]Starting fine-tuning job processing | job_id={job_id}, project_id={project_id}|"
    )

    try:
        fine_tune = fetch_by_id(session, job_id, project_id)

        storage = AmazonCloudStorage(current_user)
        document_crud = DocumentCrud(session=session, owner_id=current_user.id)
        document = document_crud.read_one(request.document_id)
        preprocessor = DataPreprocessor(document, storage, ratio)
        result = preprocessor.process()
        train_path = result["train_file"]
        test_path = result["test_file"]

        try:
            with open(train_path, "rb") as train_f:
                uploaded_train = client.files.create(file=train_f, purpose="fine-tune")
            with open(test_path, "rb") as test_f:
                uploaded_test = client.files.create(file=test_f, purpose="fine-tune")

            logger.info(
                f"[process_fine_tuning_job] Files uploaded to OpenAI successfully | "
                f"job_id={job_id}, project_id={project_id}|"
            )
        except openai.OpenAIError as e:
            error_msg = handle_openai_error(e)
            logger.error(
                f"[process_fine_tuning_job] Failed to upload to OpenAI: {error_msg} | "
                f"job_id={job_id}, project_id={project_id}|"
            )
            update_finetune_job(
                session=session,
                job=fine_tune,
                update=FineTuningUpdate(
                    status=FineTuningStatus.failed,
                    error_message="Failed during background job processing",
                ),
            )
            return
        finally:
            preprocessor.cleanup()

        training_file_id = uploaded_train.id
        testing_file_id = uploaded_test.id

        try:
            job = client.fine_tuning.jobs.create(
                training_file=training_file_id, model=request.base_model
            )
            logger.info(
                f"[process_fine_tuning_job] OpenAI fine-tuning job created | "
                f"provider_job_id={mask_string(job.id)}, job_id={job_id}, project_id={project_id}|"
            )
        except openai.OpenAIError as e:
            error_msg = handle_openai_error(e)
            logger.error(
                f"[process_fine_tuning_job] Failed to create OpenAI fine-tuning job: {error_msg} | "
                f"job_id={job_id}, project_id={project_id}|"
            )
            update_finetune_job(
                session=session,
                job=fine_tune,
                update=FineTuningUpdate(
                    status=FineTuningStatus.failed,
                    error_message="Failed during background job processing",
                ),
            )
            return

        update_finetune_job(
            session=session,
            job=fine_tune,
            update=FineTuningUpdate(
                training_file_id=training_file_id,
                testing_file_id=testing_file_id,
                split_ratio=ratio,
                provider_job_id=job.id,
                status=FineTuningStatus.running,
            ),
        )

        end_time = time.time()
        duration = end_time - start_time

        logger.info(
            f"[process_fine_tuning_job] Fine-tuning job processed successfully | "
            f"time_taken={duration:.2f}s, job_id={job_id}, project_id={project_id}|"
        )

    except Exception as e:
        logger.error(
            f"[process_fine_tuning_job] Background job failure: {e} | "
            f"job_id={job_id}, project_id={project_id}|"
        )
        update_finetune_job(
            session=session,
            job=fine_tune,
            update=FineTuningUpdate(
                status=FineTuningStatus.failed,
                error_message="Failed during background job processing",
            ),
        )


@router.post(
    "/fine-tune",
    description=load_description("fine_tuning/create.md"),
    response_model=APIResponse,
)
def fine_tune_from_CSV(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: FineTuningJobCreate,
    background_tasks: BackgroundTasks,
):
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )
    results = []

    for ratio in request.split_ratio:
        job, created = create_fine_tuning_job(
            session=session,
            request=request,
            split_ratio=ratio,
            organization_id=current_user.organization_id,
            project_id=current_user.project_id,
        )
        results.append((job, created))

        if created:
            background_tasks.add_task(
                process_fine_tuning_job,
                job.id,
                ratio,
                session,
                current_user,
                request,
                client,
            )

    if not results:
        logger.error(
            f"[fine_tune_from_CSV]All fine-tuning job creations failed for document_id={request.document_id}, project_id={current_user.project_id}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to create or fetch any fine-tuning jobs."
        )

    job_infos = [
        {
            "id": job.id,
            "document_id": job.document_id,
            "split_ratio": job.split_ratio,
            "status": job.status,
        }
        for job, _ in results
    ]

    created_count = sum(c for _, c in results)
    total = len(results)
    message = (
        "Fine-tuning job(s) started."
        if created_count == total
        else "Fine-tuning job(s) already in progress or completed."
        if created_count == 0
        else f"Started {created_count} job(s); {total - created_count} job(s) already in progress or completed."
    )

    return APIResponse.success_response({"message": message, "jobs": job_infos})


@router.get(
    "/{job_id}/refresh",
    description=load_description("fine_tuning/retrieve.md"),
    response_model=APIResponse[FineTuningJobPublic],
)
def refresh_fine_tune_status(
    job_id: int, session: SessionDep, current_user: CurrentUserOrgProject
):
    project_id = current_user.project_id
    job = fetch_by_id(session, job_id, project_id)
    client = get_openai_client(session, current_user.organization_id, project_id)

    try:
        openai_job = client.fine_tuning.jobs.retrieve(job.provider_job_id)
    except openai.OpenAIError as e:
        error_msg = handle_openai_error(e)
        logger.error(
            f"[Retrieve_fine_tune_status] Failed to retrieve OpenAI job | "
            f"provider_job_id={mask_string(job.provider_job_id)}, "
            f"error={error_msg}, job_id={job_id}, project_id={project_id}"
        )
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {error_msg}")

    mapped_status: Optional[str] = OPENAI_TO_INTERNAL_STATUS.get(
        getattr(openai_job, "status", None)
    )

    openai_error = getattr(openai_job, "error", None)
    openai_error_msg = getattr(openai_error, "message", None) if openai_error else None

    update_payload = FineTuningUpdate(
        status=mapped_status or job.status,
        fine_tuned_model=getattr(openai_job, "fine_tuned_model", None),
        error_message=openai_error_msg,
    )

    if (
        job.status != update_payload.status
        or job.fine_tuned_model != update_payload.fine_tuned_model
        or job.error_message != update_payload.error_message
    ):
        job = update_finetune_job(session=session, job=job, update=update_payload)

    return APIResponse.success_response(job)


@router.get(
    "/{document_id}",
    description="Retrieves all fine-tuning jobs associated with the given document ID for the current project",
    response_model=APIResponse[list[FineTuningJobPublic]],
)
def retrive_job_by_document(
    document_id: UUID, session: SessionDep, current_user: CurrentUserOrgProject
):
    project_id = current_user.project_id
    jobs = fetch_by_document_id(session, document_id, project_id)
    if not jobs:
        logger.warning(
            f"[retrive_job_by_document]No fine-tuning jobs found for document_id={document_id}, project_id={project_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="No fine-tuning jobs found for the given document ID",
        )
    return APIResponse.success_response(jobs)
