import secrets
import string
from sqlmodel import Session, select

from app.models import OpenAIConversation, OpenAIConversationCreate, Project
from app.crud.openai_conversation import create_conversation
from app.tests.utils.utils import get_project, get_organization


def generate_openai_id(prefix: str, length: int = 40) -> str:
    """Generate a realistic ID similar to OpenAI's format (alphanumeric only)"""
    # Generate random alphanumeric string
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}{random_part}"
