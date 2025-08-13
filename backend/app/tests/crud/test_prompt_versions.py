from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.core.util import now
from app.crud.prompt_versions import (
    create_prompt_version,
    delete_prompt_version,
    get_next_prompt_version,
)
from app.crud.prompts import create_prompt
from app.models import Prompt, PromptCreate, PromptVersion, PromptVersionCreate
from app.tests.utils.utils import get_project


@pytest.fixture
def prompt(db: Session) -> Prompt:
    """Fixture to create a reusable prompt"""
    project = get_project(db)
    prompt_data = PromptCreate(
        name=f"test_prompt_{uuid4()}",
        description="This is a test prompt",
        instruction="Test instruction",
        commit_message="Initial version"
    )
    prompt, _ = create_prompt(db, prompt_in=prompt_data, project_id=project.id)
    return prompt


def test_create_prompt_version_success(db: Session, prompt: Prompt):
    """Successfully create a new prompt version"""
    project_id = prompt.project_id
    version_data = PromptVersionCreate(
        instruction="New instruction",
        commit_message="New version"
    )
    
    prompt_version = create_prompt_version(db, prompt_id=prompt.id, prompt_version_in=version_data, project_id=project_id)
    
    assert isinstance(prompt_version, PromptVersion)
    assert prompt_version.prompt_id == prompt.id
    assert prompt_version.version == 2  # First version created by create_prompt, this is second
    assert prompt_version.instruction == version_data.instruction
    assert prompt_version.commit_message == version_data.commit_message
    assert not prompt_version.is_deleted


def test_create_prompt_version_multiple_versions(db: Session, prompt: Prompt):
    """Create multiple versions and verify correct version increment"""
    project_id = prompt.project_id
    version_data_1 = PromptVersionCreate(
        instruction="New instruction 1",
        commit_message="Version 2"
    )
    version_data_2 = PromptVersionCreate(
        instruction="New instruction 2",
        commit_message="Version 3"
    )
    
    version_1 = create_prompt_version(db, prompt_id=prompt.id, prompt_version_in=version_data_1, project_id=project_id)
    version_2 = create_prompt_version(db, prompt_id=prompt.id, prompt_version_in=version_data_2, project_id=project_id)
    
    assert version_1.version == 2
    assert version_2.version == 3
    assert version_1.instruction == "New instruction 1"
    assert version_2.instruction == "New instruction 2"


def test_create_prompt_version_prompt_not_found(db: Session):
    """Raise 404 error when prompt does not exist"""
    project = get_project(db)
    non_existent_id = uuid4()
    version_data = PromptVersionCreate(
        instruction="New instruction",
        commit_message="New version"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        create_prompt_version(db, prompt_id=non_existent_id, prompt_version_in=version_data, project_id=project.id)
    
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_create_prompt_version_deleted_prompt(db: Session, prompt: Prompt):
    """Raise 404 error when prompt is deleted"""
    project_id = prompt.project_id
    prompt.is_deleted = True
    db.add(prompt)
    db.commit()
    
    version_data = PromptVersionCreate(
        instruction="New instruction",
        commit_message="New version"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        create_prompt_version(db, prompt_id=prompt.id, prompt_version_in=version_data, project_id=project_id)
    
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_next_prompt_version(db: Session, prompt: Prompt):
    """Return incremented version number when versions exist"""
    prompt_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Second instruction",
        commit_message="Second version",
        version=2
    )
    db.add(prompt_version)
    db.commit()
    
    version = get_next_prompt_version(db, prompt_id=prompt.id)
    assert version == 3


def test_get_next_prompt_version_with_deleted_version(db: Session, prompt: Prompt):
    """Return incremented version number even if the latest version is deleted"""
    prompt_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Deleted instruction",
        commit_message="Deleted version",
        version=2,
        is_deleted=True
    )
    db.add(prompt_version)
    db.commit()
    
    version = get_next_prompt_version(db, prompt_id=prompt.id)
    assert version == 3


def test_delete_prompt_version_success(db: Session, prompt: Prompt):
    """Successfully soft-delete a non-active prompt version"""
    project_id = prompt.project_id
    
    # Create a second version (non-active)
    second_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Second instruction",
        commit_message="Second version",
        version=2
    )
    db.add(second_version)
    db.commit()
    
    delete_prompt_version(db, prompt_id=prompt.id, version_id=second_version.id, project_id=project_id)
    
    db.refresh(second_version)
    assert second_version.is_deleted
    assert second_version.deleted_at is not None
    assert second_version.deleted_at <= now()


def test_delete_prompt_version_active_version(db: Session, prompt: Prompt):
    """Raise 409 error when attempting to delete the active version"""
    project_id = prompt.project_id
    active_version_id = prompt.active_version
    
    with pytest.raises(HTTPException) as exc_info:
        delete_prompt_version(db, prompt_id=prompt.id, version_id=active_version_id, project_id=project_id)
    
    assert exc_info.value.status_code == 409
    assert "cannot delete active version" in exc_info.value.detail.lower()


def test_delete_prompt_version_not_found(db: Session, prompt: Prompt):
    """Raise 404 error when version does not exist"""
    project_id = prompt.project_id
    non_existent_version_id = uuid4()
    
    with pytest.raises(HTTPException) as exc_info:
        delete_prompt_version(db, prompt_id=prompt.id, version_id=non_existent_version_id, project_id=project_id)
    
    assert exc_info.value.status_code == 404
    assert "prompt version not found" in exc_info.value.detail.lower()


def test_delete_prompt_version_already_deleted(db: Session, prompt: Prompt):
    """Raise 404 error when attempting to delete an already deleted version"""
    project_id = prompt.project_id
    
    second_version = PromptVersion(
        prompt_id=prompt.id,
        instruction="Second instruction",
        commit_message="Second version",
        version=2,
        is_deleted=True,
        deleted_at=now()
    )
    db.add(second_version)
    db.commit()
    
    with pytest.raises(HTTPException) as exc_info:
        delete_prompt_version(db, prompt_id=prompt.id, version_id=second_version.id, project_id=project_id)
    
    assert exc_info.value.status_code == 404
    assert "prompt version not found" in exc_info.value.detail.lower()


def test_delete_prompt_version_prompt_not_found(db: Session):
    """Raise 404 error when prompt does not exist"""
    project = get_project(db)
    non_existent_prompt_id = uuid4()
    version_id = uuid4()
    
    with pytest.raises(HTTPException) as exc_info:
        delete_prompt_version(db, prompt_id=non_existent_prompt_id, version_id=version_id, project_id=project.id)
    
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()