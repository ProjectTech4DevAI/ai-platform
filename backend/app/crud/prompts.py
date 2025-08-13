import logging
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, and_, func, select

from app.core.util import now
from app.models import (
    Prompt,
    PromptCreate,
    PromptUpdate,
    PromptVersion,
    PromptWithVersion,
    PromptWithVersions,
)

logger = logging.getLogger(__name__)


def create_prompt(session: Session, prompt_in: PromptCreate, project_id: int) -> PromptWithVersion:
    """
    Create a new prompt and its first version.
    """
    prompt = Prompt(
        name=prompt_in.name,
        description=prompt_in.description,
        project_id=project_id
    )
    session.add(prompt)
    session.flush()

    version = PromptVersion(
        prompt_id=prompt.id,
        instruction=prompt_in.instruction,
        commit_message=prompt_in.commit_message,
        version=1
    )
    session.add(version)
    session.flush()

    prompt.active_version = version.id

    session.commit()
    session.refresh(prompt)

    logger.info(
        f"[create_prompt] Prompt created | id={prompt.id}, name={prompt.name}, "
        f"project_id={project_id}, version_id={version.id}"
    )

    return PromptWithVersion(
        **prompt.model_dump(),
        version=version
    )


def get_prompts(
    session: Session,
    project_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list[Prompt]:
    """Get prompts for a project."""
    stmt = (
        select(Prompt)
        .where(
            Prompt.project_id == project_id,
            Prompt.is_deleted.is_(False)
        )
        .order_by(Prompt.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return session.exec(stmt).all()


def count_prompts_in_project(session: Session, project_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(
            select(Prompt)
            .where(Prompt.project_id == project_id, Prompt.is_deleted == False)
            .subquery()
        )
    ).one()


def prompt_exists(session: Session, prompt_id: UUID, project_id: int) -> Prompt:
    """
    Check if a prompt exists for the given ID and project.
    """
    stmt = (
        select(Prompt)
        .where(
            Prompt.id == prompt_id,
            Prompt.project_id == project_id,
            Prompt.is_deleted.is_(False)
        )
    )

    prompt = session.exec(stmt).first()
    if not prompt:
        logger.error(
            f"[update_prompt] Prompt not found | prompt_id={prompt_id}, project_id={project_id}"
        )
        raise HTTPException(status_code=404, detail="Prompt not found.")

    return prompt


def get_prompt_by_id(
    session: Session,
    prompt_id: UUID,
    project_id: int,
    include_versions: bool = False
) -> PromptWithVersions:
    """
    Get a prompt by its ID, optionally including all versions.
    By default, Always returns the active version.
    """
    if include_versions:
        join_condition = and_(
            PromptVersion.prompt_id == Prompt.id,
            PromptVersion.is_deleted.is_(False)
        )
        order_by = PromptVersion.version.desc()
    else:
        join_condition = and_(
            PromptVersion.id == Prompt.active_version,
            PromptVersion.is_deleted.is_(False)
        )
        order_by = None  # no need to order when fetching only 1 row

    stmt = (
        select(Prompt, PromptVersion)
        .join(PromptVersion, join_condition, isouter=True)
        .where(
            Prompt.id == prompt_id,
            Prompt.project_id == project_id,
            Prompt.is_deleted.is_(False)
        )
    )
    if order_by is not None:
        stmt = stmt.order_by(order_by)

    results = session.exec(stmt).all()
    if not results:
        logger.error(f"[get_prompt_by_id] Prompt not found | ID: {prompt_id}, Project ID: {project_id}")
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Unpack tuples into variables
    prompt, _ = results[0] 
    versions = [version for _, version in results if version is not None]

    return PromptWithVersions(
        **prompt.model_dump(),
        versions=versions
    )


def update_prompt(
    session: Session, prompt_id: UUID, project_id: int, prompt_update: PromptUpdate
) -> Prompt:
    prompt = prompt_exists(
        session=session, prompt_id=prompt_id, project_id=project_id
    )
    update_prompt = prompt_update.model_dump(exclude_unset=True)

    active_version = update_prompt.get('active_version')
    if active_version:
        stmt = (
            select(PromptVersion)
            .where(
                PromptVersion.id == active_version,
                PromptVersion.prompt_id == prompt.id,
                PromptVersion.is_deleted.is_(False)
            )
        )
        prompt_version = session.exec(stmt).first()
        if not prompt_version:
            logger.error(
                f"[update_prompt] Prompt version not found | version_id={active_version}, prompt_id={prompt.id}"
            )
            raise HTTPException(status_code=404, detail="Invalid Active Version Id")

    if update_prompt:
        for field, value in update_prompt.items():
            setattr(prompt, field, value)
        prompt.updated_at = now()
        session.add(prompt)
        session.commit()
        session.refresh(prompt)

        logger.info(
            f"[update_prompt] Prompt updated | id={prompt.id}, name={prompt.name}, project_id={project_id}"
        )

    return prompt


def delete_prompt(session: Session, prompt_id: UUID, project_id: int) -> None:
    prompt = prompt_exists(
        session=session, prompt_id=prompt_id, project_id=project_id
    )

    prompt.is_deleted = True
    prompt.deleted_at = now()
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    logger.info(
        f"[delete_prompt] Prompt deleted | id={prompt.id}, name={prompt.name}, project_id={project_id}"
    )