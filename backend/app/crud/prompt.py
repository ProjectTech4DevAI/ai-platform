import logging

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.core.util import now
from app.models import Prompt, PromptCreate, PromptUpdate


logger = logging.getLogger(__name__)


def get_prompt_by_name_in_project(session: Session, name: str, project_id: int) -> Prompt | None:
    return session.exec(
        select(Prompt).where(
            Prompt.name == name,
            Prompt.project_id == project_id,
            Prompt.is_deleted == False
        )
    ).first()


def get_prompt_by_id(session: Session, prompt_id: int, project_id: int) -> Prompt | None:
    return session.exec(
        select(Prompt).where(
            Prompt.id == prompt_id,
            Prompt.project_id == project_id,
            Prompt.is_deleted == False,
        )
    ).first()


def get_prompt_by_project(session: Session, project_id: int, skip: int = 0, limit: int = 100) -> list[Prompt]:
    return session.exec(
        select(Prompt).where(
            Prompt.project_id == project_id,
            Prompt.is_deleted == False
        ).offset(skip).limit(limit)
    ).all()


def count_prompts_by_project(session: Session, project_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(
            select(Prompt)
            .where(Prompt.project_id == project_id, Prompt.is_deleted == False)
            .subquery()
        )
    ).one()


def create_prompt(session: Session, prompt_in: PromptCreate, project_id: int) -> Prompt:
    existing = get_prompt_by_name_in_project(
        session=session,
        name=prompt_in.name,
        project_id=project_id,
    )
    if existing:
        logger.error(
            f"[create_prompt] Prompt with this name already exists. | project_id={project_id}, name={prompt_in.name}"
        )
        raise HTTPException(status_code=409, detail="Prompt with this name already exists.")

    prompt = Prompt(
        **prompt_in.model_dump(),
        project_id=project_id,
    )
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    logger.info(f"[create_prompt] Prompt created | id={prompt.id}, name={prompt.name}, project_id={project_id}")
    return prompt


def update_prompt(session: Session, prompt_id: int, project_id: int, prompt_update: PromptUpdate) -> Prompt:
    prompt = get_prompt_by_id(session=session, prompt_id=prompt_id, project_id=project_id)
    if not prompt:
        logger.error(f"[update_prompt] Prompt not found | prompt_id={prompt_id}, project_id={project_id}")
        raise HTTPException(status_code=404, detail="Prompt not found.")

    if prompt_update.name and prompt_update.name != prompt.name:
        existing = get_prompt_by_name_in_project(
            session=session,
            name=prompt_update.name,
            project_id=project_id,
        )
        if existing:
            logger.error(
                f"[update_prompt] Prompt with this name already exists. | prompt_id={prompt_id}, project_id={project_id}, name={prompt_update.name}"
            )
            raise HTTPException(status_code=409, detail="Prompt with this name already exists.")

    update_fields = False
    if prompt_update.name:
        prompt.name = prompt_update.name
        update_fields = True
    if prompt_update.description :
        prompt.description = prompt_update.description
        update_fields = True

    if update_fields:
        prompt.updated_at = now()
        session.add(prompt)
        session.commit()
        session.refresh(prompt)

    logger.info(f"[update_prompt] Prompt updated | id={prompt.id}, name={prompt.name}, project_id={project_id}")
    return prompt


def delete_prompt(session: Session, prompt_id: int, project_id: int) -> None:
    prompt = get_prompt_by_id(session=session, prompt_id=prompt_id, project_id=project_id)
    if not prompt:
        logger.error(f"[delete_prompt] Prompt not found | prompt_id={prompt_id}, project_id={project_id}")
        raise HTTPException(status_code=404, detail="Prompt not found.")

    prompt.is_deleted = True
    prompt.deleted_at = now()
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    logger.info(f"[delete_prompt] Prompt deleted | id={prompt.id}, name={prompt.name}, project_id={project_id}")