from typing import Optional, Dict, Any, List, Union
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.models import Credential, CredsCreate, CredsUpdate
from app.core.providers import (
    validate_provider,
    validate_provider_credentials,
    get_supported_providers,
)
from app.core.security import encrypt_credentials, decrypt_credentials
from app.core.util import now
from app.core.exception_handlers import HTTPException


def set_creds_for_org(*, session: Session, creds_add: CredsCreate) -> List[Credential]:
    """Set credentials for an organization. Creates a separate row for each provider."""
    created_credentials = []

    if not creds_add.credential:
        raise HTTPException(400, "No credentials provided")

    for provider, credentials in creds_add.credential.items():
        # Validate provider and credentials
        validate_provider(provider)
        validate_provider_credentials(provider, credentials)

        # Encrypt entire credentials object
        encrypted_credentials = encrypt_credentials(credentials)

        # Create a row for each provider
        credential = Credential(
            organization_id=creds_add.organization_id,
            project_id=creds_add.project_id,
            is_active=creds_add.is_active,
            provider=provider,
            credential=encrypted_credentials,
        )
        credential.inserted_at = now()
        try:
            session.add(credential)
            session.commit()
            session.refresh(credential)
            created_credentials.append(credential)
        except IntegrityError as e:
            session.rollback()
            raise ValueError(
                f"Error while adding credentials for provider {provider}: {str(e)}"
            )

    return created_credentials


def get_key_by_org(
    *,
    session: Session,
    org_id: int,
    provider: str = "openai",
    project_id: Optional[int] = None,
) -> Optional[str]:
    """Fetches the API key from the credentials for the given organization and provider."""
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).first()

    if creds and creds.credential and "api_key" in creds.credential:
        return creds.credential["api_key"]

    return None


def get_creds_by_org(
    *, session: Session, org_id: int, project_id: Optional[int] = None
) -> List[Credential]:
    """Fetches all credentials for an organization."""
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).all()
    return creds


def get_provider_credential(
    *,
    session: Session,
    org_id: int,
    provider: str,
    project_id: Optional[int] = None,
    full: bool = False,
) -> Optional[Union[Dict[str, Any], Credential]]:
    """
    Fetches credentials for a specific provider of a project.

    Returns:
        Optional[Union[Dict[str, Any], Credential]]: If full is True, returns full Credential object.
        Otherwise returns just the decrypted credentials dict.
    """
    validate_provider(provider)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).first()

    if creds and creds.credential:
        return creds if full else decrypt_credentials(creds.credential)
    return None


def get_providers(
    *, session: Session, org_id: int, project_id: Optional[int] = None
) -> List[str]:
    """Returns a list of all active providers for which credentials are stored."""
    creds = get_creds_by_org(session=session, org_id=org_id, project_id=project_id)
    return [cred.provider for cred in creds]


def update_creds_for_org(
    *, session: Session, org_id: int, creds_in: CredsUpdate
) -> List[Credential]:
    """Updates credentials for a specific provider of an organization."""
    if not creds_in.provider or not creds_in.credential:
        raise ValueError("Provider and credential must be provided")

    validate_provider(creds_in.provider)
    validate_provider_credentials(creds_in.provider, creds_in.credential)

    # Encrypt the entire credentials object
    encrypted_credentials = encrypt_credentials(creds_in.credential)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == creds_in.provider,
        Credential.is_active == True,
        Credential.project_id == creds_in.project_id
        if creds_in.project_id is not None
        else True,
    )
    creds = session.exec(statement).first()
    if creds is None:
        raise HTTPException(
            status_code=404, detail="Credentials not found for this provider"
        )

    creds.credential = encrypted_credentials
    creds.updated_at = now()
    session.add(creds)
    session.commit()
    session.refresh(creds)

    return [creds]


def remove_provider_credential(
    session: Session, org_id: int, provider: str, project_id: Optional[int] = None
) -> Credential:
    """Remove credentials for a specific provider."""
    validate_provider(provider)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).first()

    # Soft delete
    creds.is_active = False
    creds.updated_at = now()

    session.add(creds)
    session.commit()
    session.refresh(creds)

    return creds


def remove_creds_for_org(
    *, session: Session, org_id: int, project_id: Optional[int] = None
) -> List[Credential]:
    """Removes all credentials for an organization."""
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).all()

    for cred in creds:
        cred.is_active = False
        cred.updated_at = now()
        session.add(cred)

    session.commit()
    return creds
