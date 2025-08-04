import logging
from sqlmodel import Session, select, and_
from fastapi import HTTPException
from app.models import Prompt, PromptVersion, PromptVersionCreate
from app.models import UserProjectOrg
from app.crud import get_prompt_by_id
from app.core.util import now

logger = logging.getLogger(__name__)


def get_next_prompt_version(
    session: Session, prompt_id: int
) -> int:
    """
    fetch the next prompt version for a given prompt_id and project_id
    if no next version exists, returns None
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
    current_user: UserProjectOrg,
) -> PromptVersion:

    prompt = get_prompt_by_id(
        session=session,
        prompt_id=prompt_id,
        project_id=current_user.project_id,
    )

    if not prompt:
        logger.error(f"[create_prompt_version] Prompt not found | Prompt ID: {prompt_id}, Project ID: {current_user.project_id}")
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    next_version = get_next_prompt_version(
        session=session, prompt_id=prompt_id
    )
    prompt_version = PromptVersion(
        prompt_id=prompt_id,
        version= next_version,
        instruction=prompt_version_in.instruction,
        commit_message=prompt_version_in.commit_message,
    )

    session.add(prompt_version)
    session.commit()
    session.refresh(prompt_version)
    logger.info(f"[create_prompt_version] Created new version prompt_version | Prompt ID: {prompt_id}, Version: {prompt_version.version}")
    return prompt_version


def get_prompt_version_by_id(
    session: Session, prompt_id: int, project_id: int, prompt_version_id: int
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
                PromptVersion.version == prompt_version_id,
                PromptVersion.is_deleted == False
            )
        )
        .where(
            Prompt.id == prompt_id,
            Prompt.project_id == project_id,
            Prompt.is_deleted == False
        )
    )
    
    result = session.exec(stmt).first()
    if result is None:
        return None

    prompt, prompt_version = result
    return prompt, prompt_version


def get_prompt_versions(
    session: Session, prompt_id: int, project_id: int
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
        logger.error(f"[get_prompt_versions] Prompt not found | Prompt ID: {prompt_id}, Project ID: {project_id}")
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    stmt = (
        select(PromptVersion)
        .where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.is_deleted == False
        )
        .order_by(PromptVersion.version.desc())
    )

    return session.exec(stmt).all()


def delete_prompt_version(
    session: Session, prompt_id: int, prompt_version_id: int, current_user: UserProjectOrg
) -> None:
    """
    Soft delete a prompt version by its ID.
    """
    prompt = get_prompt_by_id(
        session=session,
        prompt_id=prompt_id,
        project_id=current_user.project_id,
    )
    
    if not prompt:
        logger.error(f"[delete_prompt_version] Prompt not found | Prompt ID: {prompt_id}, Project ID: {current_user.project_id}")
        raise HTTPException(status_code=404, detail="Prompt not found")

    stmt = (
        select(PromptVersion)
        .where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.id == prompt_version_id,
            PromptVersion.is_deleted == False
        )
    )
    
    prompt_version = session.exec(stmt).first()
    
    if not prompt_version:
        logger.error(f"[delete_prompt_version] Prompt version not found | Prompt ID: {prompt_id}, Version ID: {prompt_version_id}, Project ID: {current_user.project_id}")
        raise HTTPException(status_code=404, detail="Prompt version not found")
    
    prompt_version.is_deleted = True
    prompt_version.deleted_at = now()
    session.add(prompt_version)
    session.commit()
    session.refresh(prompt_version)
    logger.info(f"[delete_prompt_version] Deleted prompt version | Prompt ID: {prompt_id}, Version ID: {prompt_version.id}")