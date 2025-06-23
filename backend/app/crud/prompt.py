from sqlmodel import Session, select
from app.models import Prompt
from typing import Optional, List
from app.core.util import now

def add_prompt(session: Session, name: str, project_id: int, organization_id: int) -> Prompt:
    if not name:
        raise ValueError("Name cannot be empty")
    if project_id <= 0:
        raise ValueError("Project ID must be a positive integer")
    if organization_id <= 0:
        raise ValueError("Organization ID must be a positive integer")
    
    prompt = Prompt(name=name, project_id=project_id, organization_id=organization_id, inserted_at=now(), updated_at=now())
    session.add(prompt)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    session.refresh(prompt)
    return prompt

def get_prompt_by_name(session: Session, name: str, project_id: int, organization_id: int) -> Optional[Prompt]:
    if not name:
        raise ValueError("Name cannot be empty")
    if project_id <= 0:
        raise ValueError("Project ID must be a positive integer")
    if organization_id <= 0:
        raise ValueError("Organization ID must be a positive integer")
    
    statement = select(Prompt).where(Prompt.project_id == project_id & Prompt.organization_id == organization_id & Prompt.name == name)
    return session.exec(statement).first()

def update_prompt(session: Session, name: str, project_id: int, organization_id: int) -> Optional[Prompt]:
    try:
        statement = select(Prompt).where(Prompt.project_id == project_id & Prompt.organization_id == organization_id & Prompt.name == name)
        prompt = session.exec(statement).first()
        if not prompt:
            raise ValueError(f"No prompt found with name '{name}' for project_id '{project_id}' and organization_id '{organization_id}'")
        prompt.updated_at = now()
        session.commit()
        session.refresh(prompt)
    except Exception as e:
        session.rollback()
        raise e
    return prompt

def list_prompts(session: Session, project_id: int, organization_id: int) -> List[Prompt]:
    if project_id <= 0:
        raise ValueError("Project ID must be a positive integer")
    if organization_id <= 0:
        raise ValueError("Organization ID must be a positive integer")
    statement = select(Prompt).where(Prompt.project_id == project_id & Prompt.organization_id == organization_id)
    return list(session.exec(statement))