from fastapi.testclient import TestClient
from sqlmodel import Session

from app.crud.prompts import create_prompt
from app.models import APIKeyPublic, PromptCreate, PromptVersion, PromptVersionCreate


def test_create_prompt_version_route_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successful creation of a prompt version via API route."""
    prompt_in = PromptCreate(
        name=f"Test Prompt",
        description="Prompt for testing version creation route",
        instruction="Initial instruction",
        commit_message="Initial version",
    )
    prompt, _ = create_prompt(
        db, prompt_in=prompt_in, project_id=user_api_key.project_id
    )

    version_in = PromptVersionCreate(
        instruction="Version 2 instructions", commit_message="Second version"
    )

    response = client.post(
        f"/api/v1/prompts/{prompt.id}/versions",
        headers={"X-API-KEY": user_api_key.key},
        json=version_in.model_dump(),
    )

    assert response.status_code == 201
    response_data = response.json()

    assert response_data["success"] is True
    assert "data" in response_data
    data = response_data["data"]
    assert data["prompt_id"] == str(prompt.id)
    assert data["instruction"] == version_in.instruction
    assert data["commit_message"] == version_in.commit_message
    assert (
        data["version"] == 2
    )  # First version created by create_prompt, this is second


def test_delete_prompt_version_route_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successful deletion of a non-active prompt version via API route"""
    prompt_in = PromptCreate(
        name=f"Test Prompt",
        description="Prompt for testing version creation route",
        instruction="Initial instruction",
        commit_message="Initial version",
    )
    prompt, _ = create_prompt(
        db, prompt_in=prompt_in, project_id=user_api_key.project_id
    )

    # Create a second version (non-active)
    second_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Second instruction",
        commit_message="Second version",
        version=2,
    )
    db.add(second_version)
    db.commit()

    response = client.delete(
        f"/api/v1/prompts/{prompt.id}/versions/{second_version.id}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"]["message"] == "Prompt version deleted successfully."

    db.refresh(second_version)
    assert second_version.is_deleted
    assert second_version.deleted_at is not None
