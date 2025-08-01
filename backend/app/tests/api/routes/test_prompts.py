from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.models import PromptCreate, APIKeyPublic, PromptUpdate, Prompt
from app.crud.prompt import get_prompt_by_name_in_project, get_prompt_by_id
from app.tests.utils.utils import get_non_existent_id


def test_create_prompt_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successful prompt creation via route."""

    prompt_data = PromptCreate(
        name="route_test_prompt",
        description="Prompt created from API test",
    )

    response = client.post(
        "/api/v1/prompt",
        headers={"X-API-KEY": user_api_key.key},
        json=prompt_data.model_dump(),
    )
    assert response.status_code == 201
    response_data = response.json()

    assert response_data["success"] is True
    assert response_data["data"]["name"] == prompt_data.name
    assert response_data["data"]["description"] == prompt_data.description
    assert response_data["data"]["project_id"] == user_api_key.project_id

    # Confirm it's persisted in DB
    db_prompt = get_prompt_by_name_in_project(
        session=db,
        name=prompt_data.name,
        project_id=user_api_key.project_id,
    )
    assert db_prompt is not None
    assert db_prompt.name == prompt_data.name


def test_update_prompt_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test successful prompt update via route."""

    # Create original prompt
    prompt_data = PromptCreate(name="original_name", description="Original desc")
    response = client.post(
        "/api/v1/prompt",
        headers={"X-API-KEY": user_api_key.key},
        json=prompt_data.model_dump(),
    )
    prompt_id = response.json()["data"]["id"]

    # Update it
    update_data = PromptUpdate(name="updated_name", description="Updated desc")
    response = client.patch(
        f"/api/v1/prompt/{prompt_id}",
        headers={"X-API-KEY": user_api_key.key},
        params=update_data.model_dump(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "updated_name"
    assert data["description"] == "Updated desc"

    # Check DB
    db_prompt = get_prompt_by_id(db, prompt_id, user_api_key.project_id)
    assert db_prompt.name == "updated_name"


def test_update_prompt_duplicate_name(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Updating prompt name to an existing name in the same project should fail."""

    # Create prompt A
    client.post(
        "/api/v1/prompt",
        headers={"X-API-KEY": user_api_key.key},
        json={"name": "prompt_a", "description": "First prompt"},
    )

    # Create prompt B
    response_b = client.post(
        "/api/v1/prompt",
        headers={"X-API-KEY": user_api_key.key},
        json={"name": "prompt_b", "description": "Second prompt"},
    )
    prompt_b_id = response_b.json()["data"]["id"]

    # Attempt to rename B to A (duplicate)
    response = client.patch(
        f"/api/v1/prompt/{prompt_b_id}",
        headers={"X-API-KEY": user_api_key.key},
        params={"name": "prompt_a"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "Prompt with this name already exists."


def test_update_prompt_not_found(
    db: Session,
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    """Updating a non-existent prompt should return 404"""

    non_existing_id = get_non_existent_id(db, Prompt)
    response = client.patch(
        f"/api/v1/prompt/{non_existing_id}",
        headers={"X-API-KEY": user_api_key.key},
        params={"name": "new_name"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Prompt not found."


from app.models import PromptCreate
from app.crud.prompt import get_prompt_by_name_in_project


def test_get_prompt_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test retrieving a prompt by ID successfully."""

    prompt_data = PromptCreate(name="get_test_prompt", description="Fetch me!")
    create_response = client.post(
        "/api/v1/prompt",
        headers={"X-API-KEY": user_api_key.key},
        json=prompt_data.model_dump(),
    )
    assert create_response.status_code == 201
    prompt_id = create_response.json()["data"]["id"]

    # Fetch prompt
    get_response = client.get(
        f"/api/v1/prompt/{prompt_id}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert get_response.status_code == 200
    data = get_response.json()["data"]
    assert data["id"] == prompt_id
    assert data["name"] == prompt_data.name
    assert data["description"] == prompt_data.description


def test_get_prompt_not_found(
    db: Session,
    client: TestClient,
    user_api_key: APIKeyPublic,
):
    """Test retrieving a prompt that does not exist."""

    non_existing_id = get_non_existent_id(db, Prompt)
    response = client.get(
        f"/api/v1/prompt/{non_existing_id}",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Prompt not found."


def test_list_prompts_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test listing prompts for a project."""

    prompt_names = ["prompt_list_1", "prompt_list_2"]
    for name in prompt_names:
        prompt_data = PromptCreate(name=name, description=f"{name} description")
        response = client.post(
            "/api/v1/prompt",
            headers={"X-API-KEY": user_api_key.key},
            json=prompt_data.model_dump(),
        )
        assert response.status_code == 201

    list_response = client.get(
        "/api/v1/prompt",
        headers={"X-API-KEY": user_api_key.key},
    )

    assert list_response.status_code == 200
    res = list_response.json()
    assert res["success"] is True
    assert isinstance(res["data"], list)
    assert len(res["data"]) >= 2

    # Ensure our prompts are in the list
    returned_names = {prompt["name"] for prompt in res["data"]}
    for name in prompt_names:
        assert name in returned_names

    # Check metadata
    assert "metadata" in res
    assert "total" in res["metadata"]


def test_delete_prompt_success(
    client: TestClient,
    db: Session,
    user_api_key: APIKeyPublic,
):
    """Test deleting a prompt via route."""

    # Create prompt
    prompt_data = PromptCreate(name="prompt_to_delete", description="To be deleted")
    create_response = client.post(
        "/api/v1/prompt",
        headers={"X-API-KEY": user_api_key.key},
        json=prompt_data.model_dump(),
    )
    assert create_response.status_code == 201
    prompt_id = create_response.json()["data"]["id"]

    # Delete prompt
    delete_response = client.delete(
        f"/api/v1/prompt/{prompt_id}",
        headers={"X-API-KEY": user_api_key.key},
    )
    assert delete_response.status_code == 200
    delete_data = delete_response.json()
    assert delete_data["success"] is True
    assert delete_data["data"]["message"] == "Prompt deleted successfully."

    # Confirm soft-delete in DB
    deleted_prompt = db.exec(
        select(Prompt).where(
            Prompt.id == prompt_id, Prompt.project_id == user_api_key.project_id
        )
    ).first()
    assert deleted_prompt is not None
    assert deleted_prompt.is_deleted is True
    assert deleted_prompt.deleted_at is not None
