import logging
from typing import Any

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
    creds = session.exec(statement).first()

    if creds and creds.credential and "api_key" in creds.credential:
        return creds.credential["api_key"]

    return None


def get_creds_by_org(
    *, session: Session, org_id: int, project_id: int
) -> list[Credential]:
    """Fetches all credentials for an organization."""
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.project_id == project_id,
    )
    creds = session.exec(statement).all()
    return creds


def get_provider_credential(
    *,
    session: Session,
    org_id: int,
    project_id: int,
    provider: str,
    full: bool = False,
) -> dict[str, Any] | Credential | None:
    """
    Fetch credentials for a specific provider within a project.

    Returns:
        dict[str, Any] | Credential | None:
            - If `full` is True, returns the full Credential SQLModel object.
            - Otherwise, returns the decrypted credentials as a dictionary.
    """
    validate_provider(provider)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.project_id == project_id,
    )
    creds = session.exec(statement).first()

    if creds and creds.credential:
        return creds if full else decrypt_credentials(creds.credential)
    return None


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
    creds = session.exec(statement).first()
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
) -> int:
    """Remove credentials for a specific provider.

    Returns:
        int: Number of rows deleted (0 or 1)
    """
    from sqlalchemy import delete

    validate_provider(provider)

    # Build delete statement
    statement = delete(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.project_id == project_id,
    )

    # Execute and get affected rows
    result = session.exec(statement)
    session.commit()

    rows_deleted = result.rowcount
    logger.info(
        f"[remove_provider_credential] Deleted {rows_deleted} credential(s) for provider {provider} | organization_id {org_id}, project_id {project_id}"
    )
    return rows_deleted


def remove_creds_for_org(*, session: Session, org_id: int, project_id: int) -> int:
    """Removes all credentials for an organization.

    Returns:
        int: Number of credentials deleted
    """
    from sqlalchemy import delete

    # Build delete statement
    statement = delete(Credential).where(
        Credential.organization_id == org_id,
        Credential.project_id == project_id,
    )

    # Execute and get affected rows
    result = session.exec(statement)
    session.commit()

    rows_deleted = result.rowcount
    logger.info(
        f"[remove_creds_for_org] Successfully deleted {rows_deleted} credential(s) | organization_id {org_id}, project_id {project_id}"
    )
    return rows_deleted
