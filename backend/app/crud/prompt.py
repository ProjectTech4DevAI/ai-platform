from sqlmodel import Session, select
from app.models import Prompt
from typing import Optional, List

def add_prompt(session: Session, name: str) -> Prompt:
    prompt = Prompt(name=name)
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return prompt

def get_prompt_by_name(session: Session, name: str) -> Optional[Prompt]:
    statement = select(Prompt).where(Prompt.name == name)
    return session.exec(statement).first()

def list_prompts(session: Session) -> List[Prompt]:
    statement = select(Prompt)
    return list(session.exec(statement))