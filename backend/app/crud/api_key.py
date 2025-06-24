import uuid
import secrets
import logging
from sqlmodel import Session, select
from app.core.security import (
    get_password_hash,
    encrypt_api_key,
    decrypt_api_key,
)
from app.core import settings
from app.core.util import now
from app.core.exception_handlers import HTTPException
from app.models.api_key import APIKey, APIKeyPublic

logger = logging.getLogger(__name__)


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash."""
    raw_key = "ApiKey " + secrets.token_urlsafe(32)
    hashed_key = get_password_hash(raw_key)
    return raw_key, hashed_key


def create_api_key(
    session: Session, organization_id: int, user_id: int, project_id: int
) -> APIKeyPublic:
    """
    Generates a new API key for an organization and associates it with a user.
    Returns the API key details with the raw key (shown only once).
    """
    # Generate raw key and its hash using the helper function
    raw_key, hashed_key = generate_api_key()
    encrypted_key = encrypt_api_key(
        raw_key
    )  # Encrypt the raw key instead of hashed key

    # Create API key record with encrypted raw key
    api_key = APIKey(
        key=encrypted_key,  # Store the encrypted raw key
        organization_id=organization_id,
        user_id=user_id,
        project_id=project_id,
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    # Set the raw key in the response (shown only once)
    api_key_dict = api_key.model_dump()
    api_key_dict["key"] = raw_key  # Return the raw key to the user

    logger.info(
        f"[create_api_key] API key creation completed | {{'api_key_id': {api_key.id}, 'user_id': {user_id}, 'project_id': {project_id}}}"
    )
    return APIKeyPublic.model_validate(api_key_dict)


def get_api_key(session: Session, api_key_id: int) -> APIKeyPublic | None:
    """
    Retrieves an API key by its ID if it exists and is not deleted.
    Returns the API key in its original format.
    """
    api_key = session.exec(
        select(APIKey).where(APIKey.id == api_key_id, APIKey.is_deleted == False)
    ).first()

    if api_key:
        # Create a copy of the API key data
        api_key_dict = api_key.model_dump()
        # Decrypt the key
        decrypted_key = decrypt_api_key(api_key.key)
        api_key_dict["key"] = decrypted_key
        return APIKeyPublic.model_validate(api_key_dict)

    logger.warning(f"[get_api_key] API key not found | {{'api_key_id': {api_key_id}}}")
    return None


def delete_api_key(session: Session, api_key_id: int) -> None:
    """
    Soft deletes (revokes) an API key by marking it as deleted.
    """
    api_key = session.get(APIKey, api_key_id)

    if not api_key:
        logger.warning(
            f"[delete_api_key] API key not found | {{'api_key_id': {api_key_id}}}"
        )
        return

    api_key.is_deleted = True
    api_key.deleted_at = now()
    api_key.updated_at = now()

    session.add(api_key)
    session.commit()
    logger.info(
        f"[delete_api_key] API key soft deleted successfully | {{'api_key_id': {api_key_id}}}"
    )


def get_api_key_by_value(session: Session, api_key_value: str) -> APIKeyPublic | None:
    """
    Retrieve an API Key record by verifying the provided key against stored hashes.
    Returns the API key in its original format.
    """
    # Get all active API keys
    api_keys = session.exec(select(APIKey).where(APIKey.is_deleted == False)).all()

    for api_key in api_keys:
        decrypted_key = decrypt_api_key(api_key.key)
        if api_key_value == decrypted_key:
            api_key_dict = api_key.model_dump()
            api_key_dict["key"] = decrypted_key
            return APIKeyPublic.model_validate(api_key_dict)

    logger.warning(
        f"[get_api_key_by_value] API key not found | {{'action': 'not_found'}}"
    )
    return None


def get_api_key_by_project_user(
    session: Session, project_id: int, user_id: uuid.UUID
) -> APIKeyPublic | None:
    """
    Retrieves the single API key associated with a project.
    """
    statement = select(APIKey).where(
        APIKey.user_id == user_id,
        APIKey.project_id == project_id,
        APIKey.is_deleted == False,
    )
    api_key = session.exec(statement).first()

    if api_key:
        api_key_dict = api_key.model_dump()
        api_key_dict["key"] = decrypt_api_key(api_key.key)
        return APIKeyPublic.model_validate(api_key_dict)

    logger.warning(
        f"[get_api_key_by_project_user] API key not found | {{'project_id': {project_id}, 'user_id': '{user_id}'}}"
    )
    return None


def get_api_keys_by_project(session: Session, project_id: int) -> list[APIKeyPublic]:
    """
    Retrieves all API keys associated with a project.
    """
    statement = select(APIKey).where(
        APIKey.project_id == project_id, APIKey.is_deleted == False
    )
    api_keys = session.exec(statement).all()

    result = []
    for key in api_keys:
        key_dict = key.model_dump()
        key_dict["key"] = decrypt_api_key(key.key)
        result.append(APIKeyPublic.model_validate(key_dict))

    return result