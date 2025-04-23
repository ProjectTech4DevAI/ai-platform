import uuid
import secrets
from datetime import datetime
from sqlmodel import Session, select

from app.models import APIKey, APIKeyPublic


# Create API Key
def create_api_key(
    session: Session, organization_id: uuid.UUID, user_id: uuid.UUID
) -> APIKeyPublic:
    """
    Generates a new API key for an organization and associates it with a user.
    """
    api_key = APIKey(
        key="ApiKey " + secrets.token_urlsafe(32),
        organization_id=organization_id,
        user_id=user_id,
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    return APIKeyPublic.model_validate(api_key)


# Get API Key by ID
def get_api_key(session: Session, api_key_id: int) -> APIKeyPublic | None:
    """
    Retrieves an API key by its ID if it exists and is not deleted.
    """
    api_key = session.exec(
        select(APIKey).where(APIKey.id == api_key_id, APIKey.is_deleted == False)
    ).first()

    return APIKeyPublic.model_validate(api_key) if api_key else None


# Get API Keys for an Organization
def get_api_keys_by_organization(
    session: Session, organization_id: uuid.UUID
) -> list[APIKeyPublic]:
    """
    Retrieves all active API keys associated with an organization.
    """
    api_keys = session.exec(
        select(APIKey).where(
            APIKey.organization_id == organization_id, APIKey.is_deleted == False
        )
    ).all()

    return [APIKeyPublic.model_validate(api_key) for api_key in api_keys]


# Soft Delete (Revoke) API Key
def delete_api_key(session: Session, api_key_id: int) -> None:
    """
    Soft deletes (revokes) an API key by marking it as deleted.
    """
    api_key = session.get(APIKey, api_key_id)

    if not api_key or api_key.is_deleted:
        raise ValueError("API key not found or already deleted")

    api_key.is_deleted = True
    api_key.deleted_at = datetime.utcnow()
    api_key.updated_at = datetime.utcnow()

    session.add(api_key)
    session.commit()


def get_api_key_by_value(session: Session, api_key_value: str) -> APIKey | None:
    """
    Retrieve an API Key record by its value.
    """
    return session.exec(
        select(APIKey).where(APIKey.key == api_key_value, APIKey.is_deleted == False)
    ).first()


def get_api_key_by_user_org(
    session: Session, organization_id: int, user_id: str
) -> APIKey | None:
    """
    Retrieve an API key for a specific user and organization.
    """
    statement = select(APIKey).where(
        APIKey.organization_id == organization_id,
        APIKey.user_id == user_id,
        APIKey.is_deleted == False,
    )
    return session.exec(statement).first()
