import pytest

from fastapi import HTTPException
from sqlmodel import Session, select

from app.crud.prompt import (
    get_prompt_by_id,
    get_prompt_by_name_in_project,
    get_prompt_by_project,
    create_prompt,
    update_prompt,
    delete_prompt,
)
from app.models import PromptCreate, PromptUpdate, Prompt
from app.tests.utils.utils import get_project, get_non_existent_id


def test_create_prompt_success(db: Session):
    """Prompt is created successfully when valid input is provided"""
    project = get_project(db)
    prompt_data = PromptCreate(
        name="test_prompt",
        description="This is a test prompt",
    )

    result = create_prompt(db, prompt_data, project_id=project.id)

    assert result.id is not None
    assert result.name == prompt_data.name
    assert result.description == prompt_data.description
    assert result.project_id == project.id
    assert not result.is_deleted
    assert result.inserted_at is not None
    assert result.updated_at is not None


def test_create_prompt_duplicate_name(db: Session):
    """Creating a prompt with a duplicate name in the same project raises an error"""
    project = get_project(db)
    prompt_data = PromptCreate(
        name="duplicate_prompt",
        description="This is a duplicate prompt",
    )

    create_prompt(db, prompt_data, project_id=project.id)

    with pytest.raises(Exception) as exc_info:
        create_prompt(
            db, prompt_data, project_id=project.id
        )  # Should raise an error due to duplicate name

    assert exc_info.value.status_code == 409


def test_update_prompt_success(db: Session):
    """Prompt is updated successfully with valid new name and description"""
    project = get_project(db)

    # Create original prompt
    prompt = create_prompt(
        db,
        PromptCreate(name="original_name", description="original description"),
        project_id=project.id,
    )

    update_data = PromptUpdate(name="updated_name", description="updated_description")
    updated = update_prompt(db, prompt.id, project.id, update_data)

    assert updated.id == prompt.id
    assert updated.name == "updated_name"
    assert updated.description == "updated_description"


def test_update_prompt_not_found(db: Session):
    """Updating a non-existent prompt raises a 404 error"""
    project = get_project(db)
    update_data = PromptUpdate(name="new_name")

    with pytest.raises(HTTPException) as exc_info:
        non_existing_id = get_non_existent_id(db, Prompt)
        update_prompt(
            db,
            prompt_id=non_existing_id,
            project_id=project.id,
            prompt_update=update_data,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_update_prompt_duplicate_name(db: Session):
    """Updating a prompt to a name that already exists in the project raises a 409 error"""
    project = get_project(db)

    # Create first prompt
    create_prompt(
        db,
        PromptCreate(
            name="existing_name",
            description="desc1",
            organization_id=project.organization_id,
        ),
        project_id=project.id,
    )

    # Create second prompt to try renaming it to the same name
    prompt2 = create_prompt(
        db,
        PromptCreate(
            name="to_rename",
            description="desc2",
            organization_id=project.organization_id,
        ),
        project_id=project.id,
    )

    update_data = PromptUpdate(name="existing_name")

    with pytest.raises(HTTPException) as exc_info:
        update_prompt(db, prompt2.id, project.id, update_data)

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail.lower()


def test_get_prompt_by_id_success(db: Session):
    """Successfully retrieves a prompt by ID within a project"""
    project = get_project(db)
    prompt = create_prompt(
        db, PromptCreate(name="prompt_by_id", description="desc"), project_id=project.id
    )

    fetched = get_prompt_by_id(db, prompt_id=prompt.id, project_id=project.id)

    assert fetched is not None
    assert fetched.id == prompt.id
    assert fetched.project_id == project.id
    assert fetched.name == "prompt_by_id"


def test_get_prompt_by_id_not_found(db: Session):
    """Returns None if the prompt ID does not exist in the project"""
    project = get_project(db)
    non_existent_id = get_non_existent_id(db, Prompt)

    result = get_prompt_by_id(db, prompt_id=non_existent_id, project_id=project.id)
    assert result is None


def test_get_prompt_by_name_in_project_success(db: Session):
    """Successfully retrieves a prompt by name within a project"""
    project = get_project(db)
    name = "prompt_by_name"
    create_prompt(
        db, PromptCreate(name=name, description="desc"), project_id=project.id
    )

    result = get_prompt_by_name_in_project(db, name=name, project_id=project.id)
    assert result is not None
    assert result.name == name
    assert result.project_id == project.id


def test_get_prompt_by_name_in_project_not_found(db: Session):
    """Returns None if no prompt matches the name in the project"""
    project = get_project(db)
    result = get_prompt_by_name_in_project(
        db, name="non_existent_name", project_id=project.id
    )
    assert result is None


def test_get_prompt_by_project_returns_all(db: Session):
    """Returns all prompts for a given project"""
    project = get_project(db)

    # Create two prompts
    create_prompt(
        db, PromptCreate(name="p1", description="desc"), project_id=project.id
    )
    create_prompt(
        db, PromptCreate(name="p2", description="desc"), project_id=project.id
    )

    prompts = get_prompt_by_project(db, project_id=project.id)
    prompt_names = [p.name for p in prompts]

    assert len(prompts) >= 2
    assert "p1" in prompt_names
    assert "p2" in prompt_names


def test_get_prompt_by_project_excludes_deleted(db: Session):
    """Deleted prompts should not appear in get_prompt_by_project results"""
    project = get_project(db)

    prompt = create_prompt(
        db,
        PromptCreate(name="active_prompt", description="desc"),
        project_id=project.id,
    )

    # Soft-delete the prompt
    prompt.is_deleted = True
    db.add(prompt)
    db.commit()

    results = get_prompt_by_project(db, project_id=project.id)
    names = [p.name for p in results]

    assert "active_prompt" not in names


def test_delete_prompt_success(db: Session):
    """Successfully soft-deletes an existing prompt"""
    project = get_project(db)

    prompt = create_prompt(
        db,
        PromptCreate(name="prompt_to_delete", description="desc"),
        project_id=project.id,
    )

    delete_prompt(db, prompt_id=prompt.id, project_id=project.id)

    # Fetch directly to check soft delete
    deleted_prompt = get_prompt_by_id(db, prompt_id=prompt.id, project_id=project.id)
    assert deleted_prompt is None

    # Query without is_deleted filter to confirm soft deletion
    result = db.exec(
        select(Prompt).where(Prompt.id == prompt.id, Prompt.project_id == project.id)
    ).first()
    assert result is not None
    assert result.is_deleted is True
    assert result.deleted_at is not None


def test_delete_prompt_not_found(db: Session):
    """Raises 404 if prompt does not exist"""
    project = get_project(db)
    non_existent_id = get_non_existent_id(db, Prompt)

    with pytest.raises(HTTPException) as exc_info:
        delete_prompt(db, prompt_id=non_existent_id, project_id=project.id)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()
