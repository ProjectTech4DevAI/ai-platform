import pytest
from unittest.mock import MagicMock, patch
from app.models import Model_Evaluation
from app.crud import fetch_by_eval_id
from app.tests.utils.test_data import (
    create_test_finetuning_job_with_extra_fields,
    create_test_model_evaluation,
)


@patch("app.api.routes.model_evaluation.ModelEvaluator")
def test_evaluate_model(
    mock_ModelEvaluator, client, db, user_api_key_header, user_api_key
):
    fine_tuned, _ = create_test_finetuning_job_with_extra_fields(db, [0.5])

    mock_evaluator = MagicMock()
    mock_evaluator.run.return_value = {"mcc": 0.8, "accuracy": 0.9}
    mock_ModelEvaluator.return_value = mock_evaluator

    body = {"fine_tuning_ids": [fine_tuned[0].id]}

    response = client.post(
        "/api/v1/model_evaluation/evaluate-model/",
        json=body,
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    json_data = response.json()

    assert json_data["data"]["message"] == "Model evaluation(s) started successfully"

    evaluations = [eval for eval in json_data["data"].get("data", []) if eval]
    assert len(evaluations) == 1

    assert evaluations[0]["status"] == "pending"

    mock_evaluator.run.assert_called_with()
    assert mock_evaluator.run.call_count == 1

    updated_model_eval = fetch_by_eval_id(
        db, evaluations[0]["id"], user_api_key.project_id
    )

    assert updated_model_eval.score == {"mcc": 0.8, "accuracy": 0.9}

    assert updated_model_eval.fine_tuning_id == fine_tuned[0].id
    assert updated_model_eval.model_name == fine_tuned[0].fine_tuned_model
    assert updated_model_eval.testing_file_id == fine_tuned[0].testing_file_id


@patch("app.api.routes.model_evaluation.ModelEvaluator")
def test_run_model_evaluation_evaluator_run_failure(
    mock_ModelEvaluator, client, db, user_api_key_header, user_api_key
):
    fine_tuned, _ = create_test_finetuning_job_with_extra_fields(db, [0.5])
    fine_tune = fine_tuned[0]

    mock_evaluator = MagicMock()
    mock_evaluator.run.side_effect = Exception("Evaluator failed")
    mock_ModelEvaluator.return_value = mock_evaluator

    response = client.post(
        "/api/v1/model_evaluation/evaluate-model/",
        json={"fine_tuning_ids": [fine_tune.id]},
        headers=user_api_key_header,
    )

    json_data = response.json()
    model_eval_id = json_data["data"]["data"][0]["id"]

    updated_model_eval = fetch_by_eval_id(db, model_eval_id, user_api_key.project_id)
    assert updated_model_eval.status == "failed"
    assert updated_model_eval.error_message == "failed during background job processing"


def test_evaluate_model_finetuning_not_found(client, db, user_api_key_header):
    invalid_fine_tune_id = 9999

    body = {"fine_tuning_ids": [invalid_fine_tune_id]}

    response = client.post(
        "/api/v1/model_evaluation/evaluate-model/",
        json=body,
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    json_data = response.json()
    assert json_data["error"] == f"Job not found"


def test_top_model_by_doc(client, db, user_api_key_header):
    model_evals = create_test_model_evaluation(db)
    model_eval = model_evals[0]

    model_eval.score = {"mcc": 0.85, "accuracy": 0.9}
    db.flush()

    response = client.get(
        f"/api/v1/model_evaluation/{model_eval.document_id}/top_model",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    json_data = response.json()

    assert json_data["data"]["score"] == {"mcc": 0.85, "accuracy": 0.9}
    assert json_data["data"]["model_name"] == model_eval.model_name
    assert json_data["data"]["document_id"] == str(model_eval.document_id)

    assert json_data["data"]["id"] == model_eval.id


def test_get_top_model_by_doc_id_no_score(client, db, user_api_key_header):
    model_evals = create_test_model_evaluation(db)

    document_id = model_evals[0].document_id

    response = client.get(
        f"/api/v1/model_evaluation/{document_id}/top_model", headers=user_api_key_header
    )

    assert response.status_code == 404

    json_data = response.json()
    assert json_data["error"] == "No top model found"


def test_get_evals_by_doc_id(client, db, user_api_key_header):
    model_evals = create_test_model_evaluation(db)
    document_id = model_evals[0].document_id

    response = client.get(
        f"/api/v1/model_evaluation/{document_id}", headers=user_api_key_header
    )

    assert response.status_code == 200
    json_data = response.json()

    assert json_data["success"] is True
    assert json_data["data"] is not None
    assert len(json_data["data"]) == 2

    evaluations = json_data["data"]
    assert all(eval["document_id"] == str(document_id) for eval in evaluations)
    assert all(eval["status"] == "pending" for eval in evaluations)
