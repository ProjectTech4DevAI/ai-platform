import logging
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, and_, select

from app.core.util import now
from app.crud.prompts import prompt_exists
from app.models import PromptVersion, PromptVersionCreate

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
    prompt_id: UUID,
    prompt_version_in: PromptVersionCreate,
    project_id: int,
) -> PromptVersion:
    """Create a new version for an existing prompt."""

    prompt_exists(
        session=session,
        prompt_id=prompt_id,
        project_id=project_id,
    )

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


def delete_prompt_version(
    session: Session, prompt_id: UUID, version_id: UUID, project_id: int
):
    """
    Delete a prompt version by ID.
    """
    prompt = prompt_exists(
        session=session,
        prompt_id=prompt_id,
        project_id=project_id,
    )
    if prompt.active_version == version_id:
        logger.error(
            f"[delete_prompt_version] Cannot delete active version | Version ID: {version_id}, Prompt ID: {prompt_id}"
        )
        raise HTTPException(status_code=409, detail="Cannot delete active version")

    stmt = select(PromptVersion).where(
        and_(
            PromptVersion.id == version_id,
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.is_deleted.is_(False),
        )
    )
    prompt_version = session.exec(stmt).first()

    if not prompt_version:
        logger.error(
            f"[delete_prompt_version] Prompt version not found | version_id={version_id}, prompt_id={prompt_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt version not found")

    prompt_version.is_deleted = True
    prompt_version.deleted_at = now()

    session.add(prompt_version)
    session.commit()
    session.refresh(prompt_version)

    logger.info(
        f"[delete_prompt_version] Deleted prompt version | Version ID: {version_id}, Prompt ID: {prompt_id}"
    )
