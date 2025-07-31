from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlmodel import Session
import logging
import time
from uuid import UUID
from app.models import (
    FineTuningJobCreate,
    FineTuningJobPublic,
)
from app.core.cloud import AmazonCloudStorage
from app.crud.document import DocumentCrud
from app.utils import get_openai_client, APIResponse
from app.crud import (
    create_fine_tuning_job,
    fetch_by_id,
    update_finetune_status,
    fetch_by_document_id,
)
from app.api.deps import CurrentUserOrgProject, SessionDep
from app.core.data_preprocess.data_preprocessing import DataPreprocessor
from app.core.util import now


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fine_tuning", tags=["fine_tuning"])


def process_fine_tuning_job(
    job_id: int,
    ratio: float,
    session: Session,
    current_user: CurrentUserOrgProject,
    request: FineTuningJobCreate,
):
    try:
        client = get_openai_client(
            session, current_user.organization_id, current_user.project_id
        )

        fine_tune = fetch_by_id(session, job_id)

        if (
            fine_tune.training_file_id
            and fine_tune.testing_file_id
            and not fine_tune.openai_job_id
        ):
            training_file_id = fine_tune.training_file_id
            testing_file_id = fine_tune.testing_file_id
        else:
            logger.info(f"[Job {job_id}] Preprocessing document {request.document_id}")
            storage = AmazonCloudStorage(current_user)
            document_crud = DocumentCrud(
                session=session, owner_id=current_user.organization_id
            )
            document = document_crud.read_one(request.document_id)

            preprocessor = DataPreprocessor(document, storage, ratio)

            try:
                result = preprocessor.process()
            except ValueError as ve:
                logger.error(f"[Job {job_id}] Preprocessing failed: {ve}")
                raise HTTPException(
                    status_code=400, detail=f"Data preprocessing failed: {str(ve)}"
                )

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
            finally:
                preprocessor.cleanup()

            training_file_id = uploaded_train.id
            testing_file_id = uploaded_test.id

        job = client.fine_tuning.jobs.create(
            training_file=training_file_id, model=request.base_model
        )

        logger.info(
            f"[Job {job_id}] OpenAI job created with ID {job.id} and status {job.status}"
        )

        fine_tune.training_file_id = training_file_id
        fine_tune.testing_file_id = testing_file_id
        fine_tune.split_ratio = ratio
        fine_tune.openai_job_id = job.id
        fine_tune.status = job.status
        fine_tune.updated_at = now()

        session.add(fine_tune)
        session.commit()

    except Exception as e:
        logger.exception(f"[Job {job_id}] Failed during background processing: {e}")
        fine_tune.status = "failed"
        fine_tune.updated_at = now()

        session.add(fine_tune)
        session.commit()


@router.post("/fine-tune", response_model=APIResponse)
def fine_tune_from_CSV(
    session: SessionDep,
    current_user: CurrentUserOrgProject,
    request: FineTuningJobCreate,
    background_tasks: BackgroundTasks,
):
    logger.info(
        f"Received fine-tune request for document={request.document_id}, base_model={request.base_model}"
    )
    job_ids = []
    created_jobs = []

    for ratio in request.split_ratio:
        try:
            existing_jobs = fetch_by_document_id(
                session=session,
                document_id=request.document_id,
                split_ratio=ratio,
                base_model=request.base_model,
            )

            if existing_jobs:
                existing_job = existing_jobs[0]
                if not existing_job.openai_job_id:
                    logger.info(
                        f"Reusing existing job {existing_job.id} without OpenAI job ID"
                    )
                    job_ids.append(existing_job.id)
                    background_tasks.add_task(
                        process_fine_tuning_job,
                        existing_job.id,
                        ratio,
                        session,
                        current_user,
                        request,
                    )
                    continue

                raise HTTPException(
                    status_code=400,
                    detail=f"Fine-tuning job already exists for document={request.document_id}, "
                    f"split_ratio={ratio}, base_model={request.base_model}",
                )

            job = create_fine_tuning_job(
                session=session,
                request=request,
                split_ratio=ratio,
                organization_id=current_user.organization_id,
                project_id=current_user.project_id,
            )

            job_ids.append(job.id)
            print("job_ids", job_ids)
            created_jobs.append(job)
            print("created_jobs=", created_jobs)

            background_tasks.add_task(
                process_fine_tuning_job, job.id, ratio, session, current_user, request
            )

        except Exception as e:
            logger.exception(
                f"Failed to schedule fine-tuning job for ratio={ratio}: {e}"
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
    job = fetch_by_id(session, job_id)

    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )

    try:
        openai_job = client.fine_tuning.jobs.retrieve(job.openai_job_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")

    if job.status != openai_job.status or (
        openai_job.fine_tuned_model
        and job.fine_tuned_model != openai_job.fine_tuned_model
    ):
        job = update_finetune_status(
            session=session,
            openai_job_id=job.openai_job_id,
            status=openai_job.status,
            fine_tuned_model=openai_job.fine_tuned_model,
        )

    return APIResponse.success_response(job)


@router.get(
    "/fine-tune/{document_id}", response_model=APIResponse[list[FineTuningJobPublic]]
)
def retrive_job_by_document(
    document_id: UUID, session: SessionDep, current_user: CurrentUserOrgProject
):
    jobs = fetch_by_document_id(session, document_id)
    if not jobs:
        raise HTTPException(
            status_code=404,
            detail="No fine-tuning jobs found for the given document ID",
        )
    return APIResponse.success_response(jobs)
