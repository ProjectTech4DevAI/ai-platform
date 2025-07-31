from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlmodel import Session
import logging
import time
import openai
from uuid import UUID
from app.models import FineTuningJobCreate, FineTuningJobPublic, FineTuningUpdate
from app.core.cloud import AmazonCloudStorage
from app.crud.document import DocumentCrud
from app.utils import get_openai_client, APIResponse, mask_string
from app.crud import (
    create_fine_tuning_job,
    fetch_by_id,
    update_finetune_job,
    fetch_by_document_id,
)
from app.api.deps import CurrentUserOrgProject, SessionDep
from app.core.finetune.preprocessing import DataPreprocessor
from app.core.util import now


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fine_tuning", tags=["fine_tuning"])


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
):
    project_id = current_user.project_id
    organization_id = current_user.organization_id
    fine_tune = None

    logger.info(
        f"Starting fine-tuning job processing: job_id={job_id}, project_id={project_id}"
    )

    try:
        client = get_openai_client(session, organization_id, project_id)
        fine_tune = fetch_by_id(session, job_id, project_id)

        if (
            fine_tune.training_file_id
            and fine_tune.testing_file_id
            and not fine_tune.openai_job_id
        ):
            logger.info(
                f"[Job {job_id}] Skipping preprocessing, using existing file IDs, project_id={project_id}"
            )
            training_file_id = fine_tune.training_file_id
            testing_file_id = fine_tune.testing_file_id
        else:
            storage = AmazonCloudStorage(current_user)
            document_crud = DocumentCrud(session=session, owner_id=organization_id)
            document = document_crud.read_one(request.document_id)

            preprocessor = DataPreprocessor(document, storage, ratio)

            try:
                result = preprocessor.process()
            except ValueError as ve:
                logger.error(
                    f"[Job {job_id}] Data preprocessing error: {ve}, project_id={project_id}"
                )
                update_finetune_job(
                    session=session,
                    job=fine_tune,
                    update=FineTuningUpdate(
                        status="failed", error_message=f"Data preprocessing error: {ve}"
                    ),
                )
                return

            train_path = result["train_file"]
            test_path = result["test_file"]

            try:
                with open(train_path, "rb") as train_f:
                    uploaded_train = client.files.create(
                        file=train_f, purpose="fine-tune"
                    )
                with open(test_path, "rb") as test_f:
                    uploaded_test = client.files.create(
                        file=test_f, purpose="fine-tune"
                    )
                logger.info(
                    f"[Job {job_id}] Files uploaded to OpenAI successfully, project_id={project_id}"
                )
            except openai.OpenAIError as e:
                error_msg = handle_openai_error(e)
                logger.error(
                    f"[Job {job_id}] Failed to upload files to OpenAI: {error_msg}, project_id={project_id}"
                )
                update_finetune_job(
                    session=session,
                    job=fine_tune,
                    update=FineTuningUpdate(
                        status="failed",
                        error_message=f"File upload to OpenAI error: {error_msg}",
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
                f"[Job {job_id}] OpenAI fine-tuning job created: openai_job_id={mask_string(job.id)}, project_id={project_id}"
            )
        except openai.OpenAIError as e:
            error_msg = handle_openai_error(e)
            logger.error(
                f"[Job {job_id}] Failed to create OpenAI fine-tuning job: {error_msg}, project_id={project_id}"
            )
            update_finetune_job(
                session=session,
                job=fine_tune,
                update=FineTuningUpdate(
                    status="failed",
                    error_message=f"Create OpenAI fine-tune job error: {error_msg}",
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
                openai_job_id=job.id,
                status=job.status,
            ),
        )

    except Exception as e:
        logger.exception(
            f"[Job {job_id}] Unhandled error during processing: {e}, project_id={project_id}"
        )
        if fine_tune:
            update_finetune_job(
                session=session,
                job=fine_tune,
                update=FineTuningUpdate(
                    status="failed", error_message=f"Background job error: {error_msg}"
                ),
            )


@router.post("/fine-tune", response_model=APIResponse)
def fine_tune_from_CSV(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: FineTuningJobCreate,
    background_tasks: BackgroundTasks,
):
    created_jobs = []

    for ratio in request.split_ratio:
        job = create_fine_tuning_job(
            session=session,
            request=request,
            split_ratio=ratio,
            organization_id=current_user.organization_id,
            project_id=current_user.project_id,
        )
        created_jobs.append(job)

        background_tasks.add_task(
            process_fine_tuning_job, job.id, ratio, session, current_user, request
        )

    if not created_jobs:
        logger.error(
            f"All fine-tuning job creations failed for document_id={request.document_id}, project_id={current_user.project_id}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to create any fine-tuning jobs."
        )

    job_infos = [
        {
            "id": job.id,
            "document_id": job.document_id,
            "split_ratio": job.split_ratio,
            "status": job.status,
            "openai_job_id": job.openai_job_id,
        }
        for job in created_jobs
    ]

    return APIResponse.success_response(
        {"message": "Fine-tuning jobs started.", "jobs": job_infos}
    )


@router.get(
    "/fine-tune/{job_id}/refresh", response_model=APIResponse[FineTuningJobPublic]
)
def refresh_fine_tune_status(
    job_id: int, session: SessionDep, current_user: CurrentUserOrgProject
):
    project_id = current_user.project_id
    job = fetch_by_id(session, job_id, project_id)
    client = get_openai_client(session, current_user.organization_id, project_id)

    try:
        openai_job = client.fine_tuning.jobs.retrieve(job.openai_job_id)
    except openai.OpenAIError as e:
        error_msg = handle_openai_error(e)
        logger.error(
            f"Failed to retrieve OpenAI job: openai_job_id={mask_string(job.openai_job_id)}, error={error_msg}, project_id={project_id}"
        )
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {error_msg}")

    openai_error_msg = (
        f"OpenAI fine-tune job error: {openai_job.error.message}"
        if getattr(openai_job, "error", None)
        else None
    )

    update_payload = FineTuningUpdate(
        status=openai_job.status,
        fine_tuned_model=openai_job.fine_tuned_model,
        error_message=openai_error_msg,
    )

    if (
        job.status != openai_job.status
        or job.fine_tuned_model != openai_job.fine_tuned_model
        or (
            getattr(openai_job, "error", None)
            and job.error_message != openai_job.error.message
        )
    ):
        job = update_finetune_job(session=session, job=job, update=update_payload)

    return APIResponse.success_response(job)


@router.get(
    "/fine-tune/{document_id}", response_model=APIResponse[list[FineTuningJobPublic]]
)
def retrive_job_by_document(
    document_id: UUID, session: SessionDep, current_user: CurrentUserOrgProject
):
    project_id = current_user.project_id
    jobs = fetch_by_document_id(session, document_id, project_id)
    if not jobs:
        logger.warning(
            f"No fine-tuning jobs found for document_id={document_id}, project_id={project_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="No fine-tuning jobs found for the given document ID",
        )
    return APIResponse.success_response(jobs)
