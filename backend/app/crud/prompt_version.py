import logging

from fastapi import HTTPException
from sqlmodel import Session, and_, select, func

from app.core.util import now
from app.crud import get_prompt_by_id
from app.models import (
    Prompt,
    PromptVersion,
    PromptVersionCreate,
    PromptVersionLabel,
    PromptVersionUpdate,
)

logger = logging.getLogger(__name__)


def get_next_prompt_version(session: Session, prompt_id: int) -> int:
    """
    fetch the next prompt version for a given prompt_id and project_id
    """

    # Not filtering is_deleted here because we want to get the next version even if the latest version is deleted
    prompt_version = session.exec(
        select(PromptVersion)
        .where(
            PromptVersion.prompt_id == prompt_id,
        )
        .order_by(PromptVersion.version.desc())
    ).first()

    return prompt_version.version + 1 if prompt_version else 1


def create_prompt_version(
    session: Session,
    prompt_id: int,
    prompt_version_in: PromptVersionCreate,
    project_id: int,
) -> PromptVersion:
    prompt = get_prompt_by_id(
        session=session,
        prompt_id=prompt_id,
        project_id=project_id,
    )

    if not prompt:
        logger.error(
            f"[create_prompt_version] Prompt not found | Prompt ID: {prompt_id}, Project ID: {project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt not found")

    next_version = get_next_prompt_version(session=session, prompt_id=prompt_id)
    prompt_version = PromptVersion(
        prompt_id=prompt_id,
        version=next_version,
        instruction=prompt_version_in.instruction,
        commit_message=prompt_version_in.commit_message,
    )

    session.add(prompt_version)
    session.commit()
    session.refresh(prompt_version)
    logger.info(
        f"[create_prompt_version] Created new version prompt_version | Prompt ID: {prompt_id}, Version: {prompt_version.version}"
    )
    return prompt_version


def get_prompt_version_by_id(
    session: Session, prompt_id: int, project_id: int, version: int
) -> PromptVersion | None:
    """
    Fetch a prompt version by its ID.
    """
    stmt = (
        select(Prompt, PromptVersion)
        .outerjoin(
            PromptVersion,
            and_(
                Prompt.id == PromptVersion.prompt_id,
                PromptVersion.version == version,
                PromptVersion.is_deleted == False,
            ),
        )
        .where(
            Prompt.id == prompt_id,
            Prompt.project_id == project_id,
            Prompt.is_deleted == False,
        )
    )

    result = session.exec(stmt).first()
    if result is None:
        logger.error(
            f"[get_prompt_version_by_id] Prompt not found | Prompt ID: {prompt_id}, Project ID: {project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt, prompt_version = result
    return prompt_version


def get_prompt_versions(
    session: Session, prompt_id: int, project_id: int, skip: int = 0, limit: int = 100
) -> list[PromptVersion]:
    """
    Fetch all prompt versions for a given prompt ID.
    """

    prompt = get_prompt_by_id(
        session=session,
        prompt_id=prompt_id,
        project_id=project_id,
    )
    if not prompt:
        logger.error(
            f"[get_prompt_versions] Prompt not found | Prompt ID: {prompt_id}, Project ID: {project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt not found")

    stmt = (
        select(PromptVersion)
        .where(PromptVersion.prompt_id == prompt_id, PromptVersion.is_deleted == False)
        .order_by(PromptVersion.version.desc())
        .offset(skip)
        .limit(limit)
    )

    return session.exec(stmt).all()


def get_prompt_versions_count(session: Session, prompt_id: int, project_id: int) -> int:
    """
    Get the count of prompt versions for a given prompt ID.
    """

    # make sure to prompt_id is valid and not deleted
    stmt = select(func.count()).where(
        PromptVersion.prompt_id == prompt_id, PromptVersion.is_deleted == False
    )

    result = session.exec(stmt).one()
    return result or 0


def get_production_prompt_version(
    session: Session, prompt_id: int, project_id: int
) -> PromptVersion | None:
    """
    Fetch the production prompt version for a given prompt ID.
    If no production version exists, returns None.
    """
    stmt = (
        select(Prompt, PromptVersion)
        .outerjoin(
            PromptVersion,
            and_(
                Prompt.id == PromptVersion.prompt_id,
                PromptVersion.label == PromptVersionLabel.PRODUCTION,
                PromptVersion.is_deleted == False,
            ),
        )
        .where(
            Prompt.id == prompt_id,
            Prompt.project_id == project_id,
            Prompt.is_deleted == False,
        )
    )
    result = session.exec(stmt).first()
    if result is None:
        logger.error(
            f"[get_production_prompt_version] Prompt not found | Prompt ID: {prompt_id}, Project ID: {project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt, prompt_version = result
    return prompt_version


def update_prompt_version(
    session: Session,
    prompt_id: int,
    project_id: int,
    version: int,
    prompt_version_in: PromptVersionUpdate,
) -> PromptVersion:
    """
    Update a prompt version by its ID.
    """
    prompt_version = get_prompt_version_by_id(
        session=session,
        prompt_id=prompt_id,
        project_id=project_id,
        version=version,
    )
    if not prompt_version:
        logger.error(
            f"[update_prompt_version] Prompt version not found | Prompt ID: {prompt_id}, Version ID: {version}, Project ID: {project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt version not found")

    if prompt_version.label == prompt_version_in.label:
        return prompt_version

    if prompt_version_in.label == PromptVersionLabel.PRODUCTION:
        # Ensure only one production version exists
        existing_production_version = get_production_prompt_version(
            session=session, prompt_id=prompt_id, project_id=project_id
        )
        if existing_production_version:
            existing_production_version.label = PromptVersionLabel.STAGING
            session.add(existing_production_version)
            logger.info(
                f"[update_prompt_version] Updated existing production version to staging | Prompt ID: {prompt_id}, Version: {existing_production_version.version}"
            )

    prompt_version.label = prompt_version_in.label
    prompt_version.updated_at = now()

    session.add(prompt_version)
    session.commit()
    session.refresh(prompt_version)

    logger.info(
        f"[update_prompt_version] Updated prompt version | Prompt ID: {prompt_id}, Version: {prompt_version.version}"
    )
    return prompt_version


def delete_prompt_version(
    session: Session, prompt_id: int, version: int, project_id: int
) -> None:
    """
    Soft delete a prompt version by its ID.
    """
    prompt_version = get_prompt_version_by_id(
        session=session,
        prompt_id=prompt_id,
        project_id=project_id,
        version=version,
    )

    if not prompt_version:
        logger.error(
            f"[delete_prompt_version] Prompt version not found | Prompt ID: {prompt_id}, Version ID: {version}, Project ID: {project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt version not found")

    prompt_version.label = (
        PromptVersionLabel.STAGING
    )  # Reset label to staging if it was production

    prompt_version.is_deleted = True
    prompt_version.deleted_at = now()

    session.add(prompt_version)
    session.commit()
    session.refresh(prompt_version)
    logger.info(
        f"[delete_prompt_version] Deleted prompt version | Prompt ID: {prompt_id}, Version ID: {prompt_version.id}"
    )
