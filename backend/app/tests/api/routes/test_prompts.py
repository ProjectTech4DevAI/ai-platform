from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.crud.prompts import create_prompt
from app.models import APIKeyPublic, PromptCreate, PromptUpdate, PromptVersion


def test_create_prompt_route_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successful creation of a prompt via API route"""
    project_id = user_api_key.project_id
    prompt_in = PromptCreate(
        name=f"test_prompt_{uuid4()}",
        description="Test prompt description",
        instruction="Test instruction",
        commit_message="Initial version",
    )

    response = client.post(
        "/api/v1/prompts/",
        headers={"X-API-KEY": user_api_key.key},
        json=prompt_in.model_dump(),
    )

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["success"] is True
    assert "data" in response_data
    data = response_data["data"]

    assert data["name"] == prompt_in.name
    assert data["description"] == prompt_in.description
    assert data["project_id"] == project_id
    assert data["inserted_at"] is not None
    assert data["updated_at"] is not None

    assert "version" in data
    assert data["version"]["instruction"] == prompt_in.instruction
    assert data["version"]["commit_message"] == prompt_in.commit_message
    assert data["version"]["version"] == 1
    assert data["active_version"] == data["version"]["id"]


def test_get_prompts_route_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successfully retrieving prompts with pagination metadata"""
    project_id = user_api_key.project_id

    # Create multiple prompts
    prompt_1_in = PromptCreate(
        name=f"prompt_1_{uuid4()}",
        description="First prompt description",
        instruction="First instruction",
        commit_message="Initial version",
    )
    prompt_2_in = PromptCreate(
        name=f"prompt_2_{uuid4()}",
        description="Second prompt description",
        instruction="Second instruction",
        commit_message="Initial version",
    )
    create_prompt(db, prompt_in=prompt_1_in, project_id=project_id)
    create_prompt(db, prompt_in=prompt_2_in, project_id=project_id)

    response = client.get(
        f"/api/v1/prompts/?skip=0&limit=100",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert "data" in response_data
    assert "metadata" in response_data
    assert response_data["metadata"]["pagination"]["total"] == 2
    assert response_data["metadata"]["pagination"]["skip"] == 0
    assert response_data["metadata"]["pagination"]["limit"] == 100

    prompts = response_data["data"]
    assert len(prompts) == 2
    assert prompts[0]["name"] == prompt_2_in.name
    assert prompts[1]["name"] == prompt_1_in.name
    assert all(prompt["project_id"] == project_id for prompt in prompts)


def test_get_prompts_route_empty(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test retrieving an empty list when no prompts exist"""
    response = client.get(
        f"/api/v1/prompts/?skip=0&limit=100",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"] == []
    assert response_data["metadata"]["pagination"]["total"] == 0
    assert response_data["metadata"]["pagination"]["skip"] == 0
    assert response_data["metadata"]["pagination"]["limit"] == 100


def test_get_prompts_route_pagination(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test retrieving prompts with specific skip and limit values"""
    project_id = user_api_key.project_id

    for i in range(3):
        prompt_in = PromptCreate(
            name=f"prompt_{i}",
            description=f"Prompt {i} description",
            instruction=f"Instruction {i}",
            commit_message="Initial version",
        )
        create_prompt(db, prompt_in=prompt_in, project_id=project_id)

    response = client.get(
        f"/api/v1/prompts/?skip=1&limit=1",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert len(response_data["data"]) == 1
    assert response_data["metadata"]["pagination"]["total"] == 3
    assert response_data["metadata"]["pagination"]["skip"] == 1
    assert response_data["metadata"]["pagination"]["limit"] == 1


def test_get_prompt_by_id_route_success_active_version(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successfully retrieving a prompt with its active version"""
    project_id = user_api_key.project_id
    prompt_in = PromptCreate(
        name=f"test_prompt_{uuid4()}",
        description="Test prompt description",
        instruction="Test instruction",
        commit_message="Initial version",
    )
    prompt, version = create_prompt(db, prompt_in=prompt_in, project_id=project_id)

    response = client.get(
        f"/api/v1/prompts/{prompt.id}?include_versions=false",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert "data" in response_data
    data = response_data["data"]

    assert data["id"] == str(prompt.id)
    assert data["name"] == prompt_in.name
    assert data["description"] == prompt_in.description
    assert data["project_id"] == project_id
    assert len(data["versions"]) == 1
    assert data["versions"][0]["id"] == str(version.id)
    assert data["versions"][0]["instruction"] == prompt_in.instruction
    assert data["versions"][0]["commit_message"] == prompt_in.commit_message
    assert data["versions"][0]["version"] == 1
    assert data["active_version"] == str(version.id)


def test_get_prompt_by_id_route_with_versions(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test retrieving a prompt with all its versions"""
    project_id = user_api_key.project_id
    prompt_in = PromptCreate(
        name=f"test_prompt_{uuid4()}",
        description="Test prompt description",
        instruction="Test instruction",
        commit_message="Initial version",
    )
    prompt, version = create_prompt(db, prompt_in=prompt_in, project_id=project_id)

    second_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Second instruction",
        commit_message="Second version",
        version=2,
    )
    db.add(second_version)
    db.commit()

    response = client.get(
        f"/api/v1/prompts/{prompt.id}?include_versions=true",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert "data" in response_data
    data = response_data["data"]

    assert len(data["versions"]) == 2
    assert data["versions"][0]["version"] == 2
    assert data["versions"][1]["version"] == 1
    assert data["versions"][0]["instruction"] == "Second instruction"
    assert data["versions"][1]["instruction"] == prompt_in.instruction


def test_get_prompt_by_id_route_not_found(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test retrieving a non-existent prompt returns 404"""
    non_existent_prompt_id = uuid4()

    response = client.get(
        f"/api/v1/prompts/{non_existent_prompt_id}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 404
    response_data = response.json()
    assert response_data["success"] is False
    assert "not found" in response_data["error"].lower()


def test_update_prompt_route_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successfully updating a prompt's name and description"""
    project_id = user_api_key.project_id
    prompt_in = PromptCreate(
        name=f"test_prompt",
        description="Test prompt description",
        instruction="Test instruction",
        commit_message="Initial version",
    )
    prompt, _ = create_prompt(db, prompt_in=prompt_in, project_id=project_id)

    prompt_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Test instruction",
        commit_message="Initial version",
        version=2,
    )
    db.add(prompt_version)
    db.commit()

    update_data = PromptUpdate(
        name="updated_prompt",
        description="Updated description",
        active_version=prompt_version.id,
    )

    response = client.patch(
        f"/api/v1/prompts/{prompt.id}",
        headers={"X-API-KEY": user_api_key.key},
        json=update_data.model_dump(mode="json", exclude_unset=True),
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert "data" in response_data
    data = response_data["data"]

    assert data["id"] == str(prompt.id)
    assert data["name"] == "updated_prompt"
    assert data["description"] == "Updated description"
    assert data["project_id"] == project_id
    assert data["active_version"] == str(prompt_version.id)


def test_delete_prompt_route_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successfully soft-deleting a prompt"""
    project_id = user_api_key.project_id
    prompt_in = PromptCreate(
        name=f"test_prompt",
        description="Test prompt description",
        instruction="Test instruction",
        commit_message="Initial version",
    )
    prompt, _ = create_prompt(db, prompt_in=prompt_in, project_id=project_id)

    response = client.delete(
        f"/api/v1/prompts/{prompt.id}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"]["message"] == "Prompt deleted successfully."

    db.refresh(prompt)
    assert prompt.is_deleted
    assert prompt.deleted_at is not None
