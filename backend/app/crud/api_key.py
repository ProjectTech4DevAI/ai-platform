import logging
import secrets
from typing import Optional, Tuple

from sqlmodel import Session, select, and_
from fastapi import HTTPException
from passlib.context import CryptContext

from app.models import APIKey
from app.crud import get_project_by_id

logger = logging.getLogger(__name__)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_api_key(session: Session, raw_key: str) -> Optional[APIKey]:
    """
    Verify an API key by extracting the prefix and checking the hash.
    Returns the APIKey record if valid, None otherwise.
    """
    try:
        # Check format: "ApiKey {key_prefix}{random_key}"
        if not raw_key.startswith("ApiKey "):
            return None

        # Extract the key part after "ApiKey "
        key_part = raw_key[7:]  # Remove "ApiKey " prefix

        # Extract key_prefix (first 22 chars - urlsafe base64 of 16 bytes)
        if len(key_part) < 22:
            return None

        key_prefix = key_part[:22]

        # Find API key by prefix
        statement = select(APIKey).where(
            and_(
                APIKey.key_prefix == key_prefix,
                APIKey.is_deleted.is_(False),
            )
        )
        api_key_record = session.exec(statement).one_or_none()

        if not api_key_record:
            return None

        # Verify hash
        if pwd_context.verify(raw_key, api_key_record.key_hash):
            return api_key_record

        return None

    except Exception as e:
        logger.error(f"[verify_api_key] Error verifying API key: {str(e)}", exc_info=True)
        return None


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key with key_prefix and hash.
    """
    random_key = secrets.token_urlsafe(32)
    key_prefix = secrets.token_urlsafe(16)

    raw_key = f"ApiKey {key_prefix}{random_key}"

    key_hash = pwd_context.hash(raw_key)

    return raw_key, key_prefix, key_hash


class APIKeyCrud:
    """
    CRUD operations for API keys scoped to a project.
    """

    def __init__(self, session: Session, project_id: int):
        self.session = session
        self.project_id = project_id

    def read_one(self, key_prefix: str) -> Optional[APIKey]:
        """
        Retrieve a single non-deleted API key by its key_prefix.
        """
        statement = select(APIKey).where(
            and_(
                APIKey.key_prefix == key_prefix,
                APIKey.project_id == self.project_id,
                APIKey.is_deleted.is_(False),
            )
        )
        return self.session.exec(statement).one_or_none()

    def read_all(self, skip: int = 0, limit: int = 100) -> list[APIKey]:
        """
        Read all non-deleted API keys for the project.
        """
        statement = (
            select(APIKey)
            .where(
                and_(
                    APIKey.project_id == self.project_id,
                    APIKey.is_deleted.is_(False),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return self.session.exec(statement).all()

    def create(
        self, user_id: int
    ) -> Tuple[str, APIKey]:
        """
        Create a new API key for the project.
        """
        try:
            raw_key, key_prefix, key_hash = generate_api_key()

            project = get_project_by_id(session=self.session, project_id=self.project_id)

            api_key = APIKey(
                key_prefix=key_prefix,
                key_hash=key_hash,
                user_id=user_id,
                organization_id=project.organization_id,
                project_id=self.project_id,
            )

            self.session.add(api_key)
            self.session.commit()
            self.session.refresh(api_key)

            logger.info(
                f"[APIKeyCrud.create_api_key] API key created successfully | "
                f"{{'api_key_id': '{api_key.id}', 'project_id': {self.project_id}, 'user_id': {user_id}}}"
            )

            return raw_key, api_key

        except Exception as e:
            logger.error(
                f"[APIKeyCrud.create_api_key] Failed to create API key | "
                f"{{'project_id': {self.project_id}, 'user_id': {user_id}, 'error': '{str(e)}'}}",
                exc_info=True,
            )
            self.session.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to create API key: {str(e)}"
            )
