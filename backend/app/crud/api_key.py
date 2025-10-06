import logging
import secrets
from uuid import UUID
from typing import Tuple

from sqlmodel import Session, select, and_
from fastapi import HTTPException
from passlib.context import CryptContext

from app.models import APIKey
from app.crud import get_project_by_id
from app.core.util import now

logger = logging.getLogger(__name__)


class APIKeyManager:
    """
    Handles API key generation and verification using secure hashing.
    Supports Backwards compatibility with old key format.
    """

    # Configuration constants
    PREFIX_NAME = "ApiKey "
    PREFIX_BYTES = 16  # Generates ~22 chars in urlsafe base64
    SECRET_BYTES = 32  # Generates ~43 chars in urlsafe base64
    PREFIX_LENGTH = 22
    KEY_LENGTH = 65  # Total length: 22 (prefix) + 43 (secret)
    HASH_ALGORITHM = "bcrypt"

    pwd_context = CryptContext(schemes=[HASH_ALGORITHM], deprecated="auto")

    @classmethod
    def generate(cls) -> Tuple[str, str, str]:
        """
        Generate a new API key with prefix and hashed value.

        Returns:
            Tuple of (raw_key, key_prefix, key_hash)
        """
        key_prefix = secrets.token_urlsafe(cls.PREFIX_BYTES)
        secret_key = secrets.token_urlsafe(cls.SECRET_BYTES)

        # Construct raw key: "ApiKey {prefix}{secret}"
        raw_key = f"{cls.PREFIX_NAME}{key_prefix}{secret_key}"

        key_hash = cls.pwd_context.hash(secret_key)

        return raw_key, key_prefix, key_hash

    @classmethod
    def _extract_key_parts(cls, raw_key: str) -> Tuple[str, str] | None:
        """
        Extract prefix and secret from an API key based on its format.

        Supports:
        - New format: "ApiKey {22-char-prefix}{43-char-secret}"
        - Old format: "ApiKey {12-char-prefix}{31-char-secret}"

        Returns:
            Tuple[str, str] -> (key_prefix, secret_to_verify)
            or None if invalid
        """
        if not raw_key.startswith(cls.PREFIX_NAME):
            return None

        key_part = raw_key[len(cls.PREFIX_NAME) :]

        if len(key_part) == cls.KEY_LENGTH:
            key_prefix = key_part[: cls.PREFIX_LENGTH]
            secret_key = key_part[cls.PREFIX_LENGTH :]
            return key_prefix, secret_key

        old_key_length = 43
        old_prefix_length = 12
        if len(key_part) == old_key_length:
            key_prefix = key_part[:old_prefix_length]
            secret_key = key_part[old_prefix_length:]
            return key_prefix, secret_key

        # Invalid format
        return None

    @classmethod
    def verify(cls, session: Session, raw_key: str) -> APIKey | None:
        """
        Verify an API key by checking its prefix and hashed value.
        Supports both old (43 chars) and new ("ApiKey " + 65 chars) formats.

        Args:
            session: Database session
            raw_key: The raw API key to verify

        Returns:
            The APIKey record if valid, None otherwise
        """
        try:
            key_parts = cls._extract_key_parts(raw_key)

            if not key_parts:
                return None

            key_prefix, secret = key_parts

            statement = select(APIKey).where(
                and_(
                    APIKey.key_prefix == key_prefix,
                    APIKey.is_deleted.is_(False),
                )
            )
            api_key_record = session.exec(statement).one_or_none()

            if not api_key_record:
                return None

            if cls.pwd_context.verify(secret, api_key_record.key_hash):
                return api_key_record

            return None

        except Exception as e:
            logger.error(
                f"[APIKeyManager.verify] Error verifying API key: {str(e)}",
                exc_info=True,
            )
            return None


api_key_manager = APIKeyManager()


class APIKeyCrud:
    """
    CRUD operations for API keys scoped to a project.
    """

    def __init__(self, session: Session, project_id: int):
        self.session = session
        self.project_id = project_id

    def read_one(self, key_id: UUID) -> APIKey | None:
        """
        Retrieve a single non-deleted API key by its key_prefix.
        """
        statement = select(APIKey).where(
            and_(
                APIKey.id == key_id,
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

    def create(self, user_id: int) -> Tuple[str, APIKey]:
        """
        Create a new API key for the project.
        """
        try:
            raw_key, key_prefix, key_hash = api_key_manager.generate()

            project = get_project_by_id(
                session=self.session, project_id=self.project_id
            )

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

    def delete(self, key_id: UUID) -> None:
        """
        Soft delete an API key by marking it as deleted.
        """
        api_key = self.read_one(key_id)
        if not api_key:
            raise HTTPException(status_code=404, detail="API Key not found")

        api_key.is_deleted = True
        api_key.deleted_at = now()
        self.session.add(api_key)
        self.session.commit()
        self.session.refresh(api_key)

        logger.info(
            f"[APIKeyCrud.delete_api_key] API key deleted successfully | "
            f"{{'api_key_id': '{api_key.id}', 'project_id': {self.project_id}}}"
        )
