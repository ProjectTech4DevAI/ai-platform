import logging
from typing import Any

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.exception_handlers import HTTPException
from app.core.providers import validate_provider, validate_provider_credentials
from app.core.security import decrypt_credentials, encrypt_credentials
from app.core.util import now
from app.models import Credential, CredsCreate, CredsUpdate

logger = logging.getLogger(__name__)


def set_creds_for_org(
    *, session: Session, creds_add: CredsCreate, organization_id: int, project_id: int
) -> list[Credential]:
    """Set credentials for an organization. Creates a separate row for each provider."""
    created_credentials = []

    if not creds_add.credential:
        logger.error(
            f"[set_creds_for_org] No credentials provided | project_id: {project_id}"
        )
        raise HTTPException(400, "No credentials provided")

    for provider, credentials in creds_add.credential.items():
        # Validate provider and credentials
        validate_provider(provider)
        validate_provider_credentials(provider, credentials)

        # Encrypt entire credentials object
        encrypted_credentials = encrypt_credentials(credentials)

        # Create a row for each provider
        credential = Credential(
            organization_id=organization_id,
            project_id=project_id,
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
            logger.error(
                f"[set_creds_for_org] Integrity error while adding credentials | organization_id {organization_id}, project_id {project_id}, provider {provider}: {str(e)}",
                exc_info=True,
            )
            # Check if it's a duplicate constraint violation
            if (
                "uq_credential_org_project_provider" in str(e)
                or "unique constraint" in str(e).lower()
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Credentials for provider '{provider}' already exist for this organization and project combination",
                )
            raise ValueError(
                f"Error while adding credentials for provider {provider}: {str(e)}"
            )
    logger.info(
        f"[set_creds_for_org] Successfully created credentials | organization_id {organization_id}, project_id {project_id}"
    )
    return created_credentials


def get_key_by_org(
    *,
    session: Session,
    org_id: int,
    project_id: int,
    provider: str = "openai",
) -> str | None:
    """Fetches the API key from the credentials for the given organization and provider."""
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.is_active.is_(True),
        Credential.project_id == project_id,
    )
    creds = session.exec(statement).one_or_none()

    if creds and creds.credential and "api_key" in creds.credential:
        return creds.credential["api_key"]

    return None


def get_creds_by_org(
    *, session: Session, org_id: int, project_id: int
) -> list[Credential]:
    """Fetches all credentials for an organization.

    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID

    Returns:
        list[Credential]: List of credentials

    Raises:
        HTTPException: If no credentials are found
    """
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.project_id == project_id,
    )
    creds = session.exec(statement).all()

    if not creds:
        logger.error(
            f"[get_creds_by_org] No credentials found | organization_id {org_id}, project_id {project_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="Credentials not found for this organization and project",
        )

    return creds


def get_provider_credential(
    *,
    session: Session,
    org_id: int,
    project_id: int,
    provider: str,
    full: bool = False,
) -> dict[str, Any] | Credential:
    """
    Fetch credentials for a specific provider within a project.

    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        provider: Provider name (e.g., 'openai', 'anthropic')
        full: If True, returns full Credential object; otherwise returns decrypted dict

    Returns:
        dict[str, Any] | Credential:
            - If `full` is True, returns the full Credential SQLModel object.
            - Otherwise, returns the decrypted credentials as a dictionary.

    Raises:
        HTTPException: If credentials are not found
    """
    validate_provider(provider)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.project_id == project_id,
    )
    creds = session.exec(statement).one_or_none()

    if creds and creds.credential:
        return creds if full else decrypt_credentials(creds.credential)

    logger.error(
        f"[get_provider_credential] Credentials not found | organization_id {org_id}, provider {provider}, project_id {project_id}"
    )
    raise HTTPException(
        status_code=404, detail=f"Credentials not found for provider '{provider}'"
    )


def get_providers(*, session: Session, org_id: int, project_id: int) -> list[str]:
    """Returns a list of all active providers for which credentials are stored."""
    creds = get_creds_by_org(session=session, org_id=org_id, project_id=project_id)
    return [cred.provider for cred in creds]


def update_creds_for_org(
    *,
    session: Session,
    org_id: int,
    project_id: int,
    creds_in: CredsUpdate,
) -> list[Credential]:
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
        Credential.is_active.is_(True),
        Credential.project_id == project_id,
    )
    creds = session.exec(statement).one_or_none()
    if creds is None:
        logger.error(
            f"[update_creds_for_org] Credentials not found | organization {org_id}, provider {creds_in.provider}, project_id {project_id}"
        )
        raise HTTPException(
            status_code=404, detail="Credentials not found for this provider"
        )

    creds.credential = encrypted_credentials
    creds.updated_at = now()
    session.add(creds)
    session.commit()
    session.refresh(creds)
    logger.info(
        f"[update_creds_for_org] Successfully updated credentials | organization_id {org_id}, provider {creds_in.provider}, project_id {project_id}"
    )
    return [creds]


def remove_provider_credential(
    session: Session, org_id: int, project_id: int, provider: str
) -> None:
    """Remove credentials for a specific provider.

    Raises:
        HTTPException: If credentials not found or deletion fails
    """
    validate_provider(provider)

    # Verify credentials exist before attempting delete
    get_provider_credential(
        session=session,
        org_id=org_id,
        project_id=project_id,
        provider=provider,
    )

    # Build delete statement
    statement = delete(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.project_id == project_id,
    )

    # Execute and get affected rows
    result = session.exec(statement)

    rows_deleted = result.rowcount
    if rows_deleted == 0:
        session.rollback()
        logger.error(
            f"[remove_provider_credential] Failed to delete credential | organization_id {org_id}, provider {provider}, project_id {project_id}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete provider credential",
        )
    session.commit()
    logger.info(
        f"[remove_provider_credential] Successfully deleted credential | provider {provider}, organization_id {org_id}, project_id {project_id}"
    )


def remove_creds_for_org(*, session: Session, org_id: int, project_id: int) -> None:
    """Removes all credentials for an organization.

    Raises:
        HTTPException: If credentials not found or deletion fails
    """
    # Verify credentials exist before attempting delete
    existing_creds = get_creds_by_org(
        session=session,
        org_id=org_id,
        project_id=project_id,
    )
    expected_count = len(existing_creds)
    statement = delete(Credential).where(
        Credential.organization_id == org_id,
        Credential.project_id == project_id,
    )
    result = session.exec(statement)

    rows_deleted = result.rowcount

    if rows_deleted < expected_count:
        logger.error(
            f"[remove_creds_for_org] Failed to delete all credentials | organization_id {org_id}, project_id {project_id}, expected {expected_count}, deleted {rows_deleted}"
        )
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete all credentials",
        )
    session.commit()
    logger.info(
        f"[remove_creds_for_org] Successfully deleted {rows_deleted} credential(s) | organization_id {org_id}, project_id {project_id}"
    )
