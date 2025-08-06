import pytest

from fastapi import HTTPException
from sqlmodel import Session

from app.models import (
    PromptVersionCreate,
    PromptVersion,
    Prompt,
    PromptCreate,
    PromptVersionLabel,
    PromptVersionUpdate,
)
from app.crud import (
    create_prompt_version,
    get_prompt_version_by_id,
    get_next_prompt_version,
    create_prompt,
    get_prompt_versions,
    get_production_prompt_version,
    get_prompt_versions_with_count,
    update_prompt_version,
    delete_prompt_version,
)
from app.tests.utils.utils import get_project, get_non_existent_id


@pytest.fixture
def prompt(db) -> Prompt:
    """Fixture to create a reusable prompt"""
    project = get_project(db)
    prompt_data = PromptCreate(
        name="test_prompt",
        description="This is a test prompt",
    )
    prompt = create_prompt(db, prompt_in=prompt_data, project_id=project.id)
    return prompt


def test_create_prompt_version_success(db, prompt: Prompt):
    version_data = PromptVersionCreate(
        instruction="First version of the prompt",
        commit_message="Initial commit",
    )

    result = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=version_data,
        project_id=prompt.project_id,
    )

    assert result is not None
    assert result.prompt_id == prompt.id
    assert result.version == 1
    assert result.instruction == "First version of the prompt"
    assert result.commit_message == "Initial commit"
    assert result.inserted_at is not None


def test_create_prompt_version_for_nonexistent_prompt(db: Session):
    project = get_project(db)
    fake_prompt_id = get_non_existent_id(db, Prompt)

    version_data = PromptVersionCreate(
        instruction="Trying to create version for fake prompt",
        commit_message="Should not work",
    )

    with pytest.raises(HTTPException) as exc_info:
        create_prompt_version(
            session=db,
            prompt_id=fake_prompt_id,
            prompt_version_in=version_data,
            project_id=project.id,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_create_multiple_prompt_versions_increments_version(
    db: Session, prompt: Prompt
):
    v1 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(instruction="v1", commit_message="init"),
        project_id=prompt.project_id,
    )

    v2 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="v2", commit_message="updated"
        ),
        project_id=prompt.project_id,
    )

    assert v1.version == 1
    assert v2.version == 2


def test_deleted_version_does_not_reset_version_number(db: Session, prompt: Prompt):
    # Create version 1
    create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(instruction="v1", commit_message="init"),
        project_id=prompt.project_id,
    )

    # Create version 2
    v2 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="v2", commit_message="second"
        ),
        project_id=prompt.project_id,
    )

    # Soft delete version 2
    v2.is_deleted = True
    db.add(v2)
    db.commit()
    db.refresh(v2)

    # Create version 3 (should not reuse 2)
    v3 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(instruction="v3", commit_message="third"),
        project_id=prompt.project_id,
    )

    assert v3.version == 3


def test_get_next_prompt_version_when_none_exist(db: Session, prompt: Prompt):
    next_version = get_next_prompt_version(db, prompt_id=prompt.id)
    assert next_version == 1


def test_get_next_prompt_version_with_existing_versions(db: Session, prompt: Prompt):
    db.add(
        PromptVersion(
            prompt_id=prompt.id,
            version=1,
            instruction="v1",
            commit_message="first commit",
        )
    )
    db.add(
        PromptVersion(
            prompt_id=prompt.id,
            version=2,
            instruction="v2",
            commit_message="second commit",
        )
    )
    db.commit()

    next_version = get_next_prompt_version(db, prompt_id=prompt.id)
    assert next_version == 3


def test_get_next_prompt_version_includes_deleted_versions(db: Session, prompt: Prompt):
    db.add(
        PromptVersion(
            prompt_id=prompt.id,
            version=1,
            instruction="v1",
            commit_message="first",
        )
    )

    # Soft-deleted version
    db.add(
        PromptVersion(
            prompt_id=prompt.id,
            version=2,
            instruction="v2",
            commit_message="second",
            is_deleted=True,
        )
    )
    db.commit()

    next_version = get_next_prompt_version(db, prompt_id=prompt.id)
    assert next_version == 3


def test_get_prompt_version_by_id_success(db: Session, prompt: Prompt):
    """Successfully retrieves the correct prompt version"""
    version_data = PromptVersionCreate(
        instruction="Test instruction",
        commit_message="Initial",
    )
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=version_data,
        project_id=prompt.project_id,
    )

    fetched = get_prompt_version_by_id(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        version=version.version,
    )

    assert fetched is not None
    assert fetched.version == version.version
    assert fetched.instruction == version_data.instruction


def test_get_prompt_version_by_id_prompt_not_found(db: Session):
    """Raises 404 if prompt does not exist"""
    project = get_project(db)
    fake_prompt_id = get_non_existent_id(db, Prompt)

    with pytest.raises(HTTPException) as exc_info:
        get_prompt_version_by_id(
            session=db,
            prompt_id=fake_prompt_id,
            project_id=project.id,
            version=1,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_prompt_version_by_id_if_version_deleted(db: Session, prompt: Prompt):
    """Returns None if the version is soft-deleted"""
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="v1",
            commit_message="first",
        ),
        project_id=prompt.project_id,
    )

    # Soft delete the version
    version.is_deleted = True
    db.add(version)
    db.commit()
    db.refresh(version)

    result = get_prompt_version_by_id(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        version=version.version,
    )

    assert result is None


def test_get_prompt_versions_success(db: Session, prompt: Prompt):
    """Should return all non-deleted prompt versions in descending order"""
    create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(instruction="v1", commit_message="init"),
        project_id=prompt.project_id,
    )

    create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="v2", commit_message="update"
        ),
        project_id=prompt.project_id,
    )

    versions = get_prompt_versions(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
    )

    assert len(versions) == 2
    assert versions[0].version == 2  # ordered descending
    assert versions[1].version == 1


def test_get_prompt_versions_excludes_deleted(db: Session, prompt: Prompt):
    """Should exclude soft-deleted prompt versions"""
    v1 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(instruction="v1", commit_message="init"),
        project_id=prompt.project_id,
    )

    v2 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="v2", commit_message="update"
        ),
        project_id=prompt.project_id,
    )

    # Soft-delete v2
    v2.is_deleted = True
    db.add(v2)
    db.commit()

    versions = get_prompt_versions(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
    )

    assert len(versions) == 1
    assert versions[0].version == 1


def test_get_prompt_versions_prompt_not_found(db: Session):
    """Should raise 404 if the prompt does not exist"""
    project = get_project(db)
    fake_prompt_id = get_non_existent_id(db, Prompt)

    with pytest.raises(HTTPException) as exc_info:
        get_prompt_versions(
            session=db,
            prompt_id=fake_prompt_id,
            project_id=project.id,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_production_prompt_version_success(db: Session, prompt: Prompt):
    """Returns the production-labeled prompt version"""
    version = PromptVersion(
        prompt_id=prompt.id,
        version=1,
        instruction="Production version",
        commit_message="Set to production",
        label=PromptVersionLabel.PRODUCTION,
    )

    db.add(version)
    db.commit()
    db.refresh(version)

    result = get_production_prompt_version(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
    )

    assert result is not None
    assert result.id == version.id
    assert result.label == PromptVersionLabel.PRODUCTION


def test_get_production_prompt_version_returns_none_if_not_set(
    db: Session, prompt: Prompt
):
    """Returns None if no production-labeled version exists"""
    create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="not prod",
            commit_message="normal version",
        ),
        project_id=prompt.project_id,
    )

    result = get_production_prompt_version(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
    )

    assert result is None


def test_get_production_prompt_version_prompt_not_found(db: Session):
    """Raises 404 if the prompt doesn't exist"""
    project = get_project(db)
    fake_id = get_non_existent_id(db, Prompt)

    with pytest.raises(HTTPException) as exc_info:
        get_production_prompt_version(
            session=db,
            prompt_id=fake_id,
            project_id=project.id,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_get_prompt_versions_with_count(db: Session, prompt: Prompt):
    """Test get_prompt_versions_with_count returns correct versions and count (excluding deleted)"""

    # Create 2 valid (non-deleted) versions
    for i in range(2):
        create_prompt_version(
            session=db,
            prompt_id=prompt.id,
            prompt_version_in=PromptVersionCreate(
                instruction=f"Instruction {i+1}",
                commit_message=f"Commit {i+1}",
            ),
            project_id=prompt.project_id,
        )

    # Create 1 deleted version
    deleted_version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="Deleted version",
            commit_message="Deleted",
        ),
        project_id=prompt.project_id,
    )
    deleted_version.is_deleted = True
    db.add(deleted_version)
    db.commit()

    versions, total = get_prompt_versions_with_count(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        skip=0,
        limit=10,
    )

    assert total == 2
    assert len(versions) == 2


def test_update_prompt_version_successfully_changes_label(db: Session, prompt: Prompt):
    """Updates label from None to STAGING"""
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="initial",
            commit_message="first",
        ),
        project_id=prompt.project_id,
    )

    updated = update_prompt_version(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        version=version.version,
        prompt_version_in=PromptVersionUpdate(label=PromptVersionLabel.STAGING),
    )

    assert updated.label == PromptVersionLabel.STAGING


def test_update_prompt_version_promotes_to_production_and_demotes_old(
    db: Session, prompt: Prompt
):
    """When promoting to PRODUCTION, existing PRODUCTION becomes STAGING"""
    # Create v1 and label as PRODUCTION
    v1 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="v1",
            commit_message="first",
        ),
        project_id=prompt.project_id,
    )
    v1.label = PromptVersionLabel.PRODUCTION
    db.add(v1)
    db.commit()

    # Create v2 with no label
    v2 = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="v2",
            commit_message="second",
        ),
        project_id=prompt.project_id,
    )

    # Promote v2 to PRODUCTION
    updated = update_prompt_version(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        version=v2.version,
        prompt_version_in=PromptVersionUpdate(label=PromptVersionLabel.PRODUCTION),
    )

    assert updated.label == PromptVersionLabel.PRODUCTION

    # Check that v1 is now STAGING
    v1_updated = get_prompt_version_by_id(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        version=v1.version,
    )

    assert v1_updated.label == PromptVersionLabel.STAGING


def test_update_prompt_version_returns_same_if_label_unchanged(
    db: Session, prompt: Prompt
):
    """If the label is unchanged, the update should return early"""
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="some",
            commit_message="init",
        ),
        project_id=prompt.project_id,
    )

    updated = update_prompt_version(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        version=version.version,
        prompt_version_in=PromptVersionUpdate(label=PromptVersionLabel.STAGING),
    )

    assert updated.label == PromptVersionLabel.STAGING


def test_update_prompt_version_raises_404_if_not_found(db: Session, prompt: Prompt):
    """Raises HTTPException 404 if version does not exist"""
    fake_version = 999
    with pytest.raises(HTTPException) as exc_info:
        update_prompt_version(
            session=db,
            prompt_id=prompt.id,
            project_id=prompt.project_id,
            version=fake_version,
            prompt_version_in=PromptVersionUpdate(label=PromptVersionLabel.PRODUCTION),
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_delete_prompt_version_soft_deletes(db: Session, prompt: Prompt):
    """Soft deletes a prompt version successfully"""
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="delete me",
            commit_message="init",
        ),
        project_id=prompt.project_id,
    )

    delete_prompt_version(
        session=db,
        prompt_id=prompt.id,
        version=version.version,
        project_id=prompt.project_id,
    )

    deleted = get_prompt_version_by_id(
        session=db,
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        version=version.version,
    )

    assert deleted is None, "Should return None because is_deleted = True"


def test_delete_prompt_version_resets_label_if_production(db: Session, prompt: Prompt):
    """Resets label from PRODUCTION to STAGING when deleted"""
    version = create_prompt_version(
        session=db,
        prompt_id=prompt.id,
        prompt_version_in=PromptVersionCreate(
            instruction="prod version",
            commit_message="commit",
            label=PromptVersionLabel.PRODUCTION,
        ),
        project_id=prompt.project_id,
    )

    delete_prompt_version(
        session=db,
        prompt_id=prompt.id,
        version=version.version,
        project_id=prompt.project_id,
    )

    # Fetch raw from DB to confirm label changed
    deleted = db.get(type(version), version.id)
    assert deleted.is_deleted is True
    assert deleted.label == PromptVersionLabel.STAGING


def test_delete_prompt_version_raises_404_if_not_found(db: Session, prompt: Prompt):
    """Raises 404 if prompt version does not exist"""
    with pytest.raises(HTTPException) as exc_info:
        delete_prompt_version(
            session=db,
            prompt_id=prompt.id,
            version=999,  # Non-existent version
            project_id=prompt.project_id,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()
