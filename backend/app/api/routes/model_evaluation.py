import logging
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlmodel import Session
from openai import OpenAI

from app.crud import (
    fetch_by_id,
    create_model_evaluation,
    fetch_by_eval_id,
    fetch_active_model_evals,
    fetch_eval_by_doc_id,
    update_model_eval,
    fetch_top_model_by_doc_id,
)
from app.models import (
    ModelEvaluationBase,
    ModelEvaluationCreate,
    ModelEvaluationStatus,
    ModelEvaluationUpdate,
    ModelEvaluationPublic,
)
from app.core.finetune.evaluation import ModelEvaluator
from app.utils import get_openai_client, APIResponse
from app.api.deps import CurrentUserOrgProject, SessionDep


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model_evaluation", tags=["model_evaluation"])


metric = ["mcc", "f1", "accuracy"]


def run_model_evaluation(
    eval_id: int,
    session: Session,
    current_user: CurrentUserOrgProject,
    client: OpenAI,
):
    start_time = time.time()

    logger.info(
        f"[run_model_evaluation] Starting evaluation | eval ID={eval_id}, project_id={current_user.project_id}"
    )

    model_eval = fetch_by_eval_id(session, eval_id, current_user.project_id)
    update_model_eval(
        session=session,
        model_eval=model_eval,
        update=ModelEvaluationUpdate(status=ModelEvaluationStatus.running),
    )

    try:
        evaluator = ModelEvaluator(
            model_name=model_eval.model_name,
            testing_file_id=model_eval.testing_file_id,
            system_prompt=model_eval.system_prompt,
            client=client,
        )
        result = evaluator.run()
        end_time = time.time()
        elapsed_time = end_time - start_time

        logger.info(
            f"[run_model_evaluation] Evaluation completed successfully | eval ID={eval_id}, "
            f"model_name={model_eval.model_name}, project_id={current_user.project_id}. "
            f"Elapsed time: {elapsed_time:.2f} seconds"
        )

        update_data = ModelEvaluationUpdate(
            score=result,
            metric=list(result.keys()),
            status=ModelEvaluationStatus.completed,
        )
        update_model_eval(
            session=session,
            model_eval=model_eval,
            update=update_data,
        )
    except Exception as e:
        end_time = time.time()
        elapsed_time = end_time - start_time

        logger.error(
            f"[run_model_evaluation] Evaluation failed | eval ID={eval_id}, project_id={current_user.project_id}: "
            f"{str(e)}. Elapsed time: {elapsed_time:.2f} seconds"
        )

        update_model_eval(
            session=session,
            model_eval=model_eval,
            update=ModelEvaluationUpdate(
                status=ModelEvaluationStatus.failed,
                error_message="failed during background job processing",
            ),
        )


@router.post("/evaluate-model/", response_model=APIResponse)
def evaluate_model(
    request: ModelEvaluationCreate,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    current_user: CurrentUserOrgProject,
):
    client = get_openai_client(
        session, current_user.organization_id, current_user.project_id
    )

    if not request.fine_tuning_ids:
        logger.error(
            f"[evaluate_model] No fine tuning IDs provided | project_id:{current_user.project_id}"
        )
        raise HTTPException(status_code=400, detail="No fine-tuned job IDs provided")

    evals: list[ModelEvaluationPublic] = []

    for job_id in request.fine_tuning_ids:
        fine_tune = fetch_by_id(session, job_id, current_user.project_id)
        active_evals = fetch_active_model_evals(
            session, job_id, current_user.project_id
        )

        if active_evals:
            logger.info(
                f"[evaluate_model] Skipping creation for {job_id}. Active evaluation exists, project_id:{current_user.project_id}"
            )
            evals.extend(
                ModelEvaluationPublic.model_validate(ev) for ev in active_evals
            )
            continue

        model_eval = create_model_evaluation(
            session=session,
            request=ModelEvaluationBase(fine_tuning_id=fine_tune.id),
            project_id=current_user.project_id,
            organization_id=current_user.organization_id,
            metric=metric,
            status=ModelEvaluationStatus.pending,
        )

        evals.append(ModelEvaluationPublic.model_validate(model_eval))

        logger.info(
            f"[evaluate_model] Created evaluation for fine_tuning_id {job_id} with eval ID={model_eval.id}, project_id:{current_user.project_id}"
        )

        background_tasks.add_task(
            run_model_evaluation, model_eval.id, session, current_user, client
        )

    return APIResponse.success_response(
        {"message": "Model evaluation(s) started successfully", "data": evals}
    )


@router.get(
    "/{document_id}/top_model", response_model=APIResponse[ModelEvaluationPublic]
)
def get_top_model_by_doc_id(
    document_id: UUID, session: SessionDep, current_user: CurrentUserOrgProject
):
    logger.info(
        f"[get_top_model_by_doc_id]Fetching top model for document_id: {document_id}, project_id: {current_user.project_id}"
    )
    top_model = fetch_top_model_by_doc_id(session, document_id, current_user.project_id)

    return APIResponse.success_response(top_model)


@router.get("/{document_id}", response_model=APIResponse[list[ModelEvaluationPublic]])
def get_evals_by_doc_id(
    document_id: UUID, session: SessionDep, current_user: CurrentUserOrgProject
):
    logger.info(
        f"[get_evals_by_doc_id]Fetching evaluations for document_id: {document_id}, project_id: {current_user.project_id}"
    )
    evaluations = fetch_eval_by_doc_id(session, document_id, current_user.project_id)
    return APIResponse.success_response(evaluations)
