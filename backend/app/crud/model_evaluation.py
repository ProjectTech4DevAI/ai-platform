from typing import Optional
import logging
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select
from sqlalchemy import func

from app.crud import fetch_by_id
from app.models import (
    Model_Evaluation,
    ModelEvaluationStatus,
    ModelEvaluationBase,
    ModelEvaluationUpdate,
)
from app.core.util import now


logger = logging.getLogger(__name__)


def create_model_evaluation(
    session: Session,
    request: ModelEvaluationBase,
    project_id: int,
    organization_id: int,
    metric: list[str],
    status: ModelEvaluationStatus = ModelEvaluationStatus.pending,
) -> Model_Evaluation:
    fine_tune = fetch_by_id(session, request.fine_tuning_id, project_id)

    if fine_tune.fine_tuned_model is None:
        logger.error(
            f"[create_model_evaluation] No fine tuned model found for the given fine tuning ID | fine_tuning_id={request.fine_tuning_id}, project_id={project_id}"
        )
        raise HTTPException(404, "Fine tuned model not found")

    base_data = {
        "fine_tuning_id": request.fine_tuning_id,
        "metric": metric,
        "system_prompt": fine_tune.system_prompt,
        "base_model": fine_tune.base_model,
        "split_ratio": fine_tune.split_ratio,
        "model_name": fine_tune.fine_tuned_model,
        "document_id": fine_tune.document_id,
        "testing_file_id": fine_tune.testing_file_id,
        "project_id": project_id,
        "organization_id": organization_id,
        "status": status,
    }

    model_eval = Model_Evaluation(**base_data)
    model_eval.updated_at = now()

    session.add(model_eval)
    session.commit()
    session.refresh(model_eval)

    logger.info(
        f"[Create_fine_tuning_job]Created new model evaluation from job ID={fine_tune.id}, project_id={project_id}"
    )
    return model_eval


def fetch_by_eval_id(
    session: Session, eval_id: int, project_id: int
) -> Model_Evaluation:
    model_eval = session.exec(
        select(Model_Evaluation).where(
            Model_Evaluation.id == eval_id, Model_Evaluation.project_id == project_id
        )
    ).one_or_none()

    if model_eval is None:
        logger.error(
            f"[fetch_by_id]Model evaluation not found for eval_id={eval_id}, project_id={project_id}"
        )
        raise HTTPException(status_code=404, detail="model eval not found")

    logger.info(
        f"[fetch_by_id]Fetched model evaluation for eval ID={model_eval.id}, project_id={project_id}"
    )
    return model_eval


def fetch_eval_by_doc_id(
    session: Session,
    document_id: UUID,
    project_id: int,
) -> list[Model_Evaluation]:
    query = (
        select(Model_Evaluation)
        .where(
            Model_Evaluation.document_id == document_id,
            Model_Evaluation.project_id == project_id,
        )
        .order_by(Model_Evaluation.updated_at.desc())
    )

    model_evals = session.exec(query).all()

    if not model_evals:
        logger.error(
            f"[fetch_eval_by_doc_id]Model evaluation not found for document_id={document_id}, project_id={project_id}"
        )
        raise HTTPException(status_code=404, detail="Model evaluation not found")

    logger.info(
        f"[fetch_eval_by_doc_id]Found {len(model_evals)} model evaluation(s) for document_id={document_id}, "
        f"project_id={project_id}, sorted by MCC"
    )

    return model_evals


def fetch_top_model_by_doc_id(
    session: Session, document_id: UUID, project_id: int
) -> Model_Evaluation:
    query = (
        select(Model_Evaluation)
        .where(
            Model_Evaluation.document_id == document_id,
            Model_Evaluation.project_id == project_id,
        )
        .order_by(Model_Evaluation.updated_at.desc())
    )

    model_evals = session.exec(query).all()

    top_model = None
    highest_mcc = -float("inf")

    for model_eval in model_evals:
        if model_eval.score is not None:
            mcc = model_eval.score.get("mcc", None)
            if mcc is not None and mcc > highest_mcc:
                highest_mcc = mcc
                top_model = model_eval

    if not top_model:
        logger.error(
            f"[fetch_top_model_by_doc_id]No model evaluation found with populated score for document_id={document_id}, project_id={project_id}"
        )
        raise HTTPException(status_code=404, detail="No top model found")

    logger.info(
        f"[fetch_top_model_by_doc_id]Found top model evaluation for document_id={document_id}, "
        f"project_id={project_id}, sorted by MCC"
    )

    return top_model


def fetch_active_model_evals(
    session: Session,
    fine_tuning_id: int,
    project_id: int,
) -> list["Model_Evaluation"]:
    """
    Return all ACTIVE model evaluations for the given document & project.
    Active = status != failed AND is_deleted is false.
    """
    stmt = (
        select(Model_Evaluation)
        .where(
            Model_Evaluation.fine_tuning_id == fine_tuning_id,
            Model_Evaluation.project_id == project_id,
            Model_Evaluation.is_deleted.is_(False),
            Model_Evaluation.status != "failed",
        )
        .order_by(Model_Evaluation.inserted_at.desc())
    )

    return session.exec(stmt).all()


def update_model_eval(
    session: Session, model_eval: Model_Evaluation, update: ModelEvaluationUpdate
) -> Model_Evaluation:
    if model_eval is None:
        raise HTTPException(status_code=404, detail="Model evaluation not found")

    logger.info(
        f"[update_model_eval] Updating model evaluation ID={model_eval.id} with status={update.status}"
    )

    for key, value in update.dict(exclude_unset=True).items():
        setattr(model_eval, key, value)

    model_eval.updated_at = now()

    session.add(model_eval)
    session.commit()
    session.refresh(model_eval)

    logger.info(
        f"[update_model_eval] Successfully updated model evaluation ID={model_eval.id}"
    )
    return model_eval
