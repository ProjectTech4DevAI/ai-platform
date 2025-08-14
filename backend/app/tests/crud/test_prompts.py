import pytest
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session

from app.core.util import now
from app.crud.prompts import (
    count_prompts_in_project,
    create_prompt,
    delete_prompt,
    get_prompt_by_id,
    get_prompts,
    prompt_exists,
    update_prompt,
)
from app.models import Prompt, PromptCreate, PromptUpdate, PromptVersion
from app.tests.utils.utils import get_project
from app.tests.utils.test_data import create_test_prompt


@pytest.fixture
def prompt(db) -> Prompt:
    """Fixture to create a reusable prompt"""
    project = get_project(db)
    prompt, _ = create_test_prompt(db, project.id)
    return prompt


def test_create_prompt_success(db: Session):
    """Prompt and its first version are created successfully when valid input is provided"""
    project = get_project(db)
    prompt_data = PromptCreate(
        name="test_prompt",
        description="This is a test prompt",
        instruction="Test instruction",
        commit_message="Initial version",
    )

    prompt, version = create_prompt(db, prompt_data, project_id=project.id)

    # Prompt checks
    assert prompt.id is not None
    assert prompt.name == prompt_data.name
    assert prompt.description == prompt_data.description
    assert prompt.project_id == project.id
    assert prompt.inserted_at is not None
    assert prompt.updated_at is not None
    assert prompt.active_version == version.id

    # Version checks
    assert version.prompt_id == prompt.id
    assert version.version == 1
    assert version.instruction == prompt_data.instruction
    assert version.commit_message == prompt_data.commit_message


def test_get_prompts_success(db: Session):
    """Retrieve prompts for a project with pagination, ensuring correct filtering and ordering"""
    project = get_project(db)

    create_prompt(
        db,
        PromptCreate(
            name="prompt1",
            description="First prompt",
            instruction="Instruction 1",
            commit_message="Initial",
        ),
        project_id=project.id,
    )
    create_prompt(
        db,
        PromptCreate(
            name="prompt2",
            description="Second prompt",
            instruction="Instruction 2",
            commit_message="Initial",
        ),
        project_id=project.id,
    )

    prompts = get_prompts(db, project_id=project.id, skip=0, limit=100)

    assert len(prompts) == 2
    assert prompts[0].name == "prompt2"
    assert prompts[1].name == "prompt1"
    assert all(not prompt.is_deleted for prompt in prompts)
    assert all(prompt.project_id == project.id for prompt in prompts)

    prompts_limited = get_prompts(db, project_id=project.id, skip=1, limit=1)
    assert len(prompts_limited) == 1
    assert prompts_limited[0].name == "prompt1"


def test_get_prompts_empty(db: Session):
    """Return empty list when no prompts exist for a project or project has no non-deleted prompts"""
    project = get_project(db)

    prompts = get_prompts(db, project_id=project.id)
    assert prompts == []

    # Create a deleted prompt
    prompt, _ = create_prompt(
        db,
        PromptCreate(
            name="deleted_prompt",
            description="Deleted",
            instruction="Instruction",
            commit_message="Initial",
        ),
        project_id=project.id,
    )
    prompt.is_deleted = True
    db.add(prompt)
    db.commit()

    prompts = get_prompts(db, project_id=project.id)
    assert prompts == []


def test_count_prompts_in_project_success(db: Session):
    """Correctly count non-deleted prompts in a project"""
    project = get_project(db)

    # Create multiple prompts
    create_prompt(
        db,
        PromptCreate(
            name="prompt1",
            description="First prompt",
            instruction="Instruction 1",
            commit_message="Initial",
        ),
        project_id=project.id,
    )
    create_prompt(
        db,
        PromptCreate(
            name="prompt2",
            description="Second prompt",
            instruction="Instruction 2",
            commit_message="Initial",
        ),
        project_id=project.id,
    )

    count = count_prompts_in_project(db, project_id=project.id)
    assert count == 2


def test_count_prompts_in_project_empty_or_deleted(db: Session):
    """Return 0 when no prompts exist or all prompts are deleted"""
    project = get_project(db)

    # Test empty project
    count = count_prompts_in_project(db, project_id=project.id)
    assert count == 0

    # Create a deleted prompt
    prompt, _ = create_prompt(
        db,
        PromptCreate(
            name="deleted_prompt",
            description="Deleted",
            instruction="Instruction",
            commit_message="Initial",
        ),
        project_id=project.id,
    )
    prompt.is_deleted = True
    db.add(prompt)
    db.commit()

    count = count_prompts_in_project(db, project_id=project.id)
    assert count == 0


def test_prompt_exists_success(db: Session, prompt: Prompt):
    """Successfully retrieve an existing prompt by ID and project"""
    project = get_project(db)  # Call get_project as a function
    result = prompt_exists(db, prompt_id=prompt.id, project_id=project.id)

    assert isinstance(result, Prompt)
    assert result.id == prompt.id
    assert result.project_id == project.id
    assert result.name == prompt.name
    assert result.description == prompt.description
    assert not result.is_deleted


def test_prompt_exists_not_found(db: Session):
    """Raise 404 error when prompt ID does not exist"""
    project = get_project(db)  # Call get_project as a function
    non_existent_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        prompt_exists(db, prompt_id=non_existent_id, project_id=project.id)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_prompt_exists_deleted_prompt(db: Session, prompt: Prompt):
    """Raise 404 error when prompt is deleted"""
    project_id = prompt.project_id
    prompt.is_deleted = True
    db.add(prompt)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        prompt_exists(db, prompt_id=prompt.id, project_id=project_id)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_prompt_by_id_success_active_version(db: Session, prompt: Prompt):
    """Retrieve a prompt by ID with only its active version"""
    project = get_project(db)
    retrieved_prompt, versions = get_prompt_by_id(
        db, prompt_id=prompt.id, project_id=project.id, include_versions=False
    )

    assert isinstance(retrieved_prompt, Prompt)
    assert isinstance(versions, list)
    assert len(versions) == 1
    assert retrieved_prompt.id == prompt.id
    assert retrieved_prompt.name == prompt.name
    assert retrieved_prompt.description == prompt.description
    assert retrieved_prompt.project_id == project.id
    assert not retrieved_prompt.is_deleted
    assert versions[0].id == prompt.active_version
    assert versions[0].instruction == "Test instruction"
    assert versions[0].commit_message == "Initial version"
    assert versions[0].version == 1
    assert not versions[0].is_deleted


def test_get_prompt_by_id_with_versions(db: Session, prompt: Prompt):
    """Retrieve a prompt by ID with all its versions"""
    project = get_project(db)

    # Add another version
    new_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Updated instruction",
        commit_message="Second version",
        version=2,
    )
    db.add(new_version)
    db.commit()

    retrieved_prompt, versions = get_prompt_by_id(
        db, prompt_id=prompt.id, project_id=project.id, include_versions=True
    )

    assert isinstance(retrieved_prompt, Prompt)
    assert isinstance(versions, list)
    assert len(versions) == 2
    assert retrieved_prompt.id == prompt.id
    assert retrieved_prompt.name == prompt.name
    assert retrieved_prompt.description == prompt.description
    assert retrieved_prompt.project_id == project.id
    assert not retrieved_prompt.is_deleted
    assert versions[0].version == 2  # Latest version first (descending order)
    assert versions[1].version == 1
    assert versions[0].instruction == "Updated instruction"
    assert versions[1].instruction == "Test instruction"
    assert not any(version.is_deleted for version in versions)


def test_get_prompt_by_id_not_found(db: Session):
    """Raise 404 error when prompt ID does not exist"""
    project = get_project(db)
    non_existent_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        get_prompt_by_id(db, prompt_id=non_existent_id, project_id=project.id)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_prompt_by_id_deleted_prompt(db: Session, prompt: Prompt):
    """Raise 404 error when prompt is deleted"""
    project_id = prompt.project_id
    prompt.is_deleted = True
    db.add(prompt)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_prompt_by_id(db, prompt_id=prompt.id, project_id=project_id)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_prompt_by_id_deleted_version(db: Session, prompt: Prompt):
    """Exclude deleted versions when retrieving prompt versions"""
    project_id = prompt.project_id

    deleted_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Deleted instruction",
        commit_message="Deleted version",
        version=2,
        is_deleted=True,
    )
    db.add(deleted_version)
    db.commit()

    retrieved_prompt, versions = get_prompt_by_id(
        db, prompt_id=prompt.id, project_id=project_id, include_versions=True
    )

    assert isinstance(retrieved_prompt, Prompt)
    assert isinstance(versions, list)
    assert len(versions) == 1
    assert versions[0].version == 1
    assert not versions[0].is_deleted
    assert versions[0].instruction == "Test instruction"


def test_update_prompt_success_name_description(db: Session, prompt: Prompt):
    """Successfully update prompt's name and description"""
    project_id = prompt.project_id
    update_data = PromptUpdate(name="updated_prompt", description="Updated description")

    updated_prompt = update_prompt(
        db, prompt_id=prompt.id, project_id=project_id, prompt_update=update_data
    )

    assert isinstance(updated_prompt, Prompt)
    assert updated_prompt.id == prompt.id
    assert updated_prompt.name == "updated_prompt"
    assert updated_prompt.description == "Updated description"
    assert updated_prompt.project_id == project_id
    assert not updated_prompt.is_deleted


def test_update_prompt_success_active_version(db: Session, prompt: Prompt):
    """Successfully update prompt's active version"""
    project_id = prompt.project_id

    # Create a new version
    new_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="New instruction",
        commit_message="Second version",
        version=2,
    )
    db.add(new_version)
    db.commit()

    update_data = PromptUpdate(active_version=new_version.id)
    updated_prompt = update_prompt(
        db, prompt_id=prompt.id, project_id=project_id, prompt_update=update_data
    )

    assert isinstance(updated_prompt, Prompt)
    assert updated_prompt.id == prompt.id
    assert updated_prompt.active_version == new_version.id


def test_update_prompt_invalid_active_version(db: Session, prompt: Prompt):
    """Raise 404 error when updating with an invalid active version ID"""
    project_id = prompt.project_id
    invalid_version_id = uuid4()

    update_data = PromptUpdate(active_version=invalid_version_id)

    with pytest.raises(HTTPException) as exc_info:
        update_prompt(
            db, prompt_id=prompt.id, project_id=project_id, prompt_update=update_data
        )

    assert exc_info.value.status_code == 404
    assert "invalid active version id" in exc_info.value.detail.lower()


def test_update_prompt_not_found(db: Session):
    """Raise 404 error when prompt does not exist"""
    project = get_project(db)
    non_existent_id = uuid4()
    update_data = PromptUpdate(name="new_name")

    with pytest.raises(HTTPException) as exc_info:
        update_prompt(
            db,
            prompt_id=non_existent_id,
            project_id=project.id,
            prompt_update=update_data,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_delete_prompt_success(db: Session, prompt: Prompt):
    """Successfully soft delete a prompt"""
    project_id = prompt.project_id

    delete_prompt(db, prompt_id=prompt.id, project_id=project_id)

    db.refresh(prompt)
    assert prompt.is_deleted
    assert prompt.deleted_at is not None
    assert prompt.deleted_at <= now()


def test_delete_prompt_not_found(db: Session):
    """Raise 404 error when deleting a non-existent prompt"""
    project = get_project(db)
    non_existent_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        delete_prompt(db, prompt_id=non_existent_id, project_id=project.id)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_delete_prompt_already_deleted(db: Session, prompt: Prompt):
    """Raise 404 error when attempting to delete an already deleted prompt"""
    project_id = prompt.project_id
    prompt.is_deleted = True
    prompt.deleted_at = now()
    db.add(prompt)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        delete_prompt(db, prompt_id=prompt.id, project_id=project_id)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()
