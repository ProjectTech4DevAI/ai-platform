from typing import Optional, List, Tuple
from sqlmodel import Session, select, and_

from app.core.util import now
from app.models import Assistant


def get_assistant_by_id(session: Session, assistant_id: str) -> Optional[Assistant]:
    """Get an assistant by its OpenAI assistant ID."""
    statement = select(Assistant).where(and_(Assistant.assistant_id == assistant_id))
    return session.exec(statement).first()
