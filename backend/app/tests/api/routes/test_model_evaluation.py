from unittest.mock import patch, MagicMock

from app.tests.utils.test_data import (
    create_test_finetuning_job_with_extra_fields,
    create_test_model_evaluation,
)
from app.models import ModelEvaluation


@patch("app.api.routes.model_evaluation.ModelEvaluator")
@patch("app.api.routes.model_evaluation.get_cloud_storage")
@patch("app.api.routes.model_evaluation.get_openai_client")
def test_evaluate_model_background_success(
    mock_get_client,
    mock_get_storage,
    mock_evaluator_cls,
    client,
    db,
    user_api_key_header,
):
    fine_tuned, _ = create_test_finetuning_job_with_extra_fields(db, [0.5])
    body = {"fine_tuning_ids": [fine_tuned[0].id]}

    evaluator = MagicMock()
    evaluator.run.return_value = {
        "evaluation_score": 0.87,
        "prediction_data_s3_object": "s3://bucket/preds.csv",
    }
    mock_evaluator_cls.return_value = evaluator

    with patch("app.api.routes.model_evaluation.Session") as SessionMock:
        SessionMock.return_value.__enter__.return_value = db
        SessionMock.return_value.__exit__.return_value = None

        resp = client.post(
            "/api/v1/model_evaluation/evaluate_models/",
            json=body,
            headers=user_api_key_header,
        )

    assert resp.status_code == 200, resp.text

    payload = resp.json()

    eval_id = payload["data"]["data"][0]["id"]

    ev = db.get(ModelEvaluation, eval_id)
    assert ev is not None, "evaluation row should exist after background task"
    db.refresh(ev)

    assert ev.status == "completed"
    assert ev.score == 0.87
    assert ev.prediction_data_s3_object == "s3://bucket/preds.csv"
    assert not ev.error_message


def test_evaluate_model_finetuning_not_found(client, user_api_key_header):
    invalid_fine_tune_id = 9999

    body = {"fine_tuning_ids": [invalid_fine_tune_id]}

    response = client.post(
        "/api/v1/model_evaluation/evaluate_models/",
        json=body,
        headers=user_api_key_header,
    )

    assert response.status_code == 404
    json_data = response.json()
    assert json_data["error"] == f"Job not found"


def test_top_model_by_doc(client, db, user_api_key_header):
    model_evals = create_test_model_evaluation(db)
    model_eval = model_evals[0]

    model_eval.score = {
        "mcc": 0.85,
    }
    db.flush()

    response = client.get(
        f"/api/v1/model_evaluation/{model_eval.document_id}/top_model",
        headers=user_api_key_header,
    )

    assert response.status_code == 200
    json_data = response.json()

    assert json_data["data"]["score"] == {
        "mcc": 0.85,
    }
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
