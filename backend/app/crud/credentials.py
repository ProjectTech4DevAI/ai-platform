from typing import Optional, Dict, Any, List
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.models import Credential, CredsCreate, CredsUpdate
from app.core.providers import (
    validate_provider,
    validate_provider_credentials,
    get_supported_providers,
)
from app.core.security import encrypt_api_key, decrypt_api_key


def set_creds_for_org(*, session: Session, creds_add: CredsCreate) -> List[Credential]:
    """Set credentials for an organization. Creates a separate row for each provider."""
    created_credentials = []

    if not creds_add.credential:
        raise ValueError("No credentials provided")

    for provider, credentials in creds_add.credential.items():
        # Validate provider and credentials
        validate_provider(provider)
        validate_provider_credentials(provider, credentials)

        # Encrypt API key if present
        if isinstance(credentials, dict) and "api_key" in credentials:
            credentials["api_key"] = encrypt_api_key(credentials["api_key"])

        # Create a row for each provider
        credential = Credential(
            organization_id=creds_add.organization_id,
            project_id=creds_add.project_id,
            is_active=creds_add.is_active,
            provider=provider,
            credential=credentials,
        )
        credential.inserted_at = datetime.utcnow()
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
    """Fetches all active credentials for the given organization."""
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    return session.exec(statement).all()


def get_provider_credential(
    *, session: Session, org_id: int, provider: str, project_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Fetches credentials for a specific provider of an organization."""
    validate_provider(provider)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).first()

    if creds and creds.credential:
        # Decrypt api_key if present
        if "api_key" in creds.credential:
            try:
                creds.credential["api_key"] = decrypt_api_key(
                    creds.credential["api_key"]
                )
            except Exception as e:
                raise ValueError(f"Failed to decrypt API key: {str(e)}")
        return creds.credential
    return None


def get_providers(
    *, session: Session, org_id: int, project_id: Optional[int] = None
) -> List[str]:
    """Returns a list of all active providers for which credentials are stored."""
    creds = get_creds_by_org(session=session, org_id=org_id, project_id=project_id)
    return [cred.provider for cred in creds]


def update_creds_for_org(
    session: Session, org_id: int, creds_in: CredsUpdate
) -> List[Credential]:
    if not creds_in:
        raise ValueError(
            "Missing request body or failed to parse JSON into CredsUpdate"
        )

    """Update credentials for an organization. Can update specific provider or add new provider."""
    if not creds_in.provider or not creds_in.credential:
        raise ValueError("Provider and credential information must be provided")

    # Validate provider and credentials
    validate_provider(creds_in.provider)
    validate_provider_credentials(creds_in.provider, creds_in.credential)

    # Encrypt API key if present
    if isinstance(creds_in.credential, dict) and "api_key" in creds_in.credential:
        creds_in.credential["api_key"] = encrypt_api_key(creds_in.credential["api_key"])

    # Check if credentials exist for this provider
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == creds_in.provider,
        Credential.project_id == creds_in.project_id
        if creds_in.project_id is not None
        else True,
    )
    existing_cred = session.exec(statement).first()

    if existing_cred:
        # Update existing credentials
        existing_cred.credential = creds_in.credential
        existing_cred.is_active = (
            creds_in.is_active if creds_in.is_active is not None else True
        )
        if creds_in.project_id is not None:
            existing_cred.project_id = creds_in.project_id
        existing_cred.updated_at = datetime.utcnow()
        try:
            session.add(existing_cred)
            session.commit()
            session.refresh(existing_cred)
            return [existing_cred]
        except IntegrityError as e:
            session.rollback()
            raise ValueError(f"Error while updating credentials: {str(e)}")
    else:
        # Check if there are any other active credentials for this provider in the organization
        if creds_in.project_id is not None:
            other_creds = session.exec(
                select(Credential).where(
                    Credential.organization_id == org_id,
                    Credential.provider == creds_in.provider,
                    Credential.project_id == creds_in.project_id,
                    Credential.is_active == True,
                )
            ).first()
            if other_creds:
                raise ValueError(
                    f"Active credentials for provider '{creds_in.provider}' already exist for this organization and project combination"
                )

        # Create new credentials
        new_cred = Credential(
            organization_id=org_id,
            provider=creds_in.provider,
            credential=creds_in.credential,
            project_id=creds_in.project_id,
            is_active=creds_in.is_active if creds_in.is_active is not None else True,
        )
        try:
            session.add(new_cred)
            session.commit()
            session.refresh(new_cred)
            return [new_cred]
        except IntegrityError as e:
            session.rollback()
            raise ValueError(f"Error while creating credentials: {str(e)}")


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

    if not creds:
        raise ValueError(f"Credentials not found for provider '{provider}'")

    # Soft delete by setting is_active to False
    creds.is_active = False
    creds.updated_at = datetime.utcnow()

    try:
        session.add(creds)
        session.commit()
        session.refresh(creds)
        return creds
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"Error while removing provider credentials: {str(e)}")


def remove_creds_for_org(
    session: Session, org_id: int, project_id: Optional[int] = None
):
    """
    Removes all credentials for a specific organization by marking them as inactive.
    Returns the list of updated credentials or None if no credentials were found.
    """
    creds = session.exec(
        select(Credential).where(
            Credential.organization_id == org_id,
            Credential.is_active == True,
            Credential.project_id == project_id if project_id is not None else True,
        )
    ).all()

    if not creds:
        return None  # Return None if no credentials are found

    for cred in creds:
        cred.is_active = False
        cred.deleted_at = datetime.utcnow()
        session.add(cred)

    session.commit()
    return creds
