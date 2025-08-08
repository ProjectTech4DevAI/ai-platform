from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import (
    PromptCreate,
    PromptVersionCreate,
    APIKeyPublic,
    PromptVersionLabel,
    PromptVersionUpdate,
)
from app.crud import create_prompt, create_prompt_version


def test_create_prompt_version_route_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successful creation of a prompt version via API route."""

    # Setup: Create prompt for the test
    prompt_in = PromptCreate(
        name="api_version_test_prompt",
        description="Prompt for testing version creation route",
    )
    prompt = create_prompt(db, prompt_in=prompt_in, project_id=user_api_key.project_id)

    version_in = PromptVersionCreate(
        instruction="Version 1 instructions",
        commit_message="Initial version",
    )

    response = client.post(
        f"/api/v1/prompt/{prompt.id}/version",
        headers={"X-API-KEY": user_api_key.key},
        json=version_in.model_dump(),
    )

    # Assertions
    assert response.status_code == 201
    response_data = response.json()

    assert response_data["success"] is True
    data = response_data["data"]
    assert data["prompt_id"] == prompt.id
    assert data["instruction"] == version_in.instruction
    assert data["commit_message"] == version_in.commit_message
    assert data["version"] == 1
    assert data["label"] == "staging"


def test_get_prompt_version_by_id_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    # Create a prompt
    prompt_in = PromptCreate(name="get-version-prompt", description="desc")
    prompt = create_prompt(db, prompt_in=prompt_in, project_id=user_api_key.project_id)

    # Create a prompt version
    version_in = PromptVersionCreate(
        instruction="Retrieve this version",
        commit_message="initial",
    )
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=version_in,
        project_id=user_api_key.project_id,
    )

    # Call the API route
    response = client.get(
        f"/api/v1/prompt/{prompt.id}/version/{version.version}",
        headers={"X-API-KEY": user_api_key.key},
    )

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["version"] == version.version
    assert data["data"]["instruction"] == version.instruction
    assert data["data"]["commit_message"] == version.commit_message


def test_get_prompt_version_by_id_failure(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    # Create a prompt
    prompt_in = PromptCreate(name="get-version-prompt", description="desc")
    prompt = create_prompt(db, prompt_in=prompt_in, project_id=user_api_key.project_id)

    # Call the API route
    response = client.get(
        f"/api/v1/prompt/{prompt.id}/version/9999",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_get_prompt_versions_with_pagination(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    prompt = create_prompt(
        db,
        prompt_in=PromptCreate(
            name="versioned-prompt", description="Prompt with versions"
        ),
        project_id=user_api_key.project_id,
    )

    for i in range(5):
        create_prompt_version(
            session=db,
            prompt_id=prompt.id,
            prompt_version_in=PromptVersionCreate(
                instruction=f"Instruction {i + 1}", commit_message=f"Commit {i + 1}"
            ),
            project_id=user_api_key.project_id,
        )

    skip = 0
    limit = 3
    response = client.get(
        f"/api/v1/prompt/{prompt.id}/versions",
        headers={"X-API-KEY": user_api_key.key},
        params={"skip": skip, "limit": limit},
    )

    # Step 4: Assertions
    assert response.status_code == 200
    body = response.json()

    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) == limit

    metadata = body["metadata"]
    assert "pagination" in metadata
    assert metadata["pagination"]["total"] == 5
    assert metadata["pagination"]["skip"] == skip
    assert metadata["pagination"]["limit"] == limit

    # Basic content check
    for item in body["data"]:
        assert item["prompt_id"] == prompt.id
        assert "instruction" in item
        assert "commit_message" in item


def test_update_prompt_version_route_to_production(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    # Create prompt
    prompt = create_prompt(
        db,
        prompt_in=PromptCreate(name="update-version", description="for patch test"),
        project_id=user_api_key.project_id,
    )

    # Create version
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="Make it prod",
            commit_message="initial commit",
        ),
        project_id=user_api_key.project_id,
    )

    # Update version to PRODUCTION
    update_payload = PromptVersionUpdate(label=PromptVersionLabel.PRODUCTION)
    response = client.patch(
        f"/api/v1/prompt/{prompt.id}/version/{version.version}",
        json=update_payload.model_dump(),
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["label"] == PromptVersionLabel.PRODUCTION
    assert data["data"]["version"] == version.version


def test_delete_prompt_version_route(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    prompt = create_prompt(
        db,
        prompt_in=PromptCreate(name="delete-version", description="for delete test"),
        project_id=user_api_key.project_id,
    )

    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="To be deleted",
            commit_message="deleting this",
        ),
        project_id=user_api_key.project_id,
    )

    response = client.delete(
        f"/api/v1/prompt/{prompt.id}/version/{version.version}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted" in data["data"]["message"].lower()
