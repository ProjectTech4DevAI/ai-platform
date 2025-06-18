import logging
from typing import Optional, Dict, Any, List
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

logger = logging.getLogger(__name__)


def set_creds_for_org(*, session: Session, creds_add: CredsCreate) -> List[Credential]:
    """Set credentials for an organization. Creates a separate row for each provider."""
    logger.info(
        f"[set_creds_for_org] Starting credential creation | {{'org_id': {creds_add.organization_id}, 'project_id': {creds_add.project_id}, 'provider_count': {len(creds_add.credential)}}}"
    )
    if not creds_add.credential:
        logger.error(
            f"[set_creds_for_org] No credentials provided | {{'org_id': {creds_add.organization_id}}}"
        )
        raise HTTPException(400, "No credentials provided")

    created_credentials = []
    for provider, credentials in creds_add.credential.items():
        logger.info(
            f"[set_creds_for_org] Processing credentials for provider | {{'org_id': {creds_add.organization_id}, 'provider': '{provider}'}}"
        )
        # Validate provider and credentials
        validate_provider(provider)
        validate_provider_credentials(provider, credentials)

        # Encrypt entire credentials object
        encrypted_credentials = encrypt_credentials(credentials)
        logger.info(
            f"[set_creds_for_org] Credentials encrypted | {{'org_id': {creds_add.organization_id}, 'provider': '{provider}'}}"
        )

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
            logger.info(
                f"[set_creds_for_org] Credential created successfully | {{'org_id': {creds_add.organization_id}, 'provider': '{provider}', 'credential_id': {credential.id}}}"
            )
        except IntegrityError as e:
            session.rollback()
            logger.error(
                f"[set_creds_for_org] Integrity error while adding credentials | {{'org_id': {creds_add.organization_id}, 'provider': '{provider}', 'error': '{str(e)}'}}"
            )
            raise ValueError(
                f"Error while adding credentials for provider {provider}: {str(e)}"
            )

    logger.info(
        f"[set_creds_for_org] Credentials creation completed | {{'org_id': {creds_add.organization_id}, 'credential_count': {len(created_credentials)}}}"
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
    logger.info(
        f"[get_key_by_org] Retrieving API key | {{'org_id': {org_id}, 'provider': '{provider}', 'project_id': {project_id}}}"
    )
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).first()

    if creds and creds.credential and "api_key" in creds.credential:
        logger.info(
            f"[get_key_by_org] API key retrieved successfully | {{'org_id': {org_id}, 'provider': '{provider}', 'credential_id': {creds.id}}}"
        )
        return creds.credential["api_key"]

    logger.warning(
        f"[get_key_by_org] No API key found | {{'org_id': {org_id}, 'provider': '{provider}', 'project_id': {project_id}}}"
    )
    return None


def get_creds_by_org(
    *, session: Session, org_id: int, project_id: Optional[int] = None
) -> List[Credential]:
    """Fetches all credentials for an organization."""
    logger.info(
        f"[get_creds_by_org] Retrieving all credentials | {{'org_id': {org_id}, 'project_id': {project_id}}}"
    )
    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).all()
    logger.info(
        f"[get_creds_by_org] Credentials retrieved successfully | {{'org_id': {org_id}, 'credential_count': {len(creds)}}}"
    )
    return creds


def get_provider_credential(
    *, session: Session, org_id: int, provider: str, project_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Fetches credentials for a specific provider of an organization."""
    logger.info(
        f"[get_provider_credential] Retrieving credentials for provider | {{'org_id': {org_id}, 'provider': '{provider}', 'project_id': {project_id}}}"
    )
    validate_provider(provider)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.is_active == True,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).first()

    if creds and creds.credential:
        decrypted_credentials = decrypt_credentials(creds.credential)
        logger.info(
            f"[get_provider_credential] Credentials retrieved and decrypted | {{'org_id': {org_id}, 'provider': '{provider}', 'credential_id': {creds.id}}}"
        )
        return decrypted_credentials
    logger.warning(
        f"[get_provider_credential] No credentials found | {{'org_id': {org_id}, 'provider': '{provider}', 'project_id': {project_id}}}"
    )
    return None


def get_providers(
    *, session: Session, org_id: int, project_id: Optional[int] = None
) -> List[str]:
    """Returns a list of all active providers for which credentials are stored."""
    logger.info(
        f"[get_providers] Retrieving active providers | {{'org_id': {org_id}, 'project_id': {project_id}}}"
    )
    creds = get_creds_by_org(session=session, org_id=org_id, project_id=project_id)
    providers = [cred.provider for cred in creds]
    logger.info(
        f"[get_providers] Providers retrieved successfully | {{'org_id': {org_id}, 'provider_count': {len(providers)}}}"
    )
    return providers


def update_creds_for_org(
    *, session: Session, org_id: int, creds_in: CredsUpdate
) -> List[Credential]:
    """Updates credentials for a specific provider of an organization."""
    logger.info(
        f"[update_creds_for_org] Starting credential update | {{'org_id': {org_id}, 'provider': '{creds_in.provider}', 'project_id': {creds_in.project_id}}}"
    )
    if not creds_in.provider or not creds_in.credential:
        logger.error(
            f"[update_creds_for_org] Missing provider or credential | {{'org_id': {org_id}}}"
        )
        raise ValueError("Provider and credential must be provided")

    validate_provider(creds_in.provider)
    validate_provider_credentials(creds_in.provider, creds_in.credential)

    # Encrypt the entire credentials object
    encrypted_credentials = encrypt_credentials(creds_in.credential)
    logger.info(
        f"[update_creds_for_org] Credentials encrypted | {{'org_id': {org_id}, 'provider': '{creds_in.provider}'}}"
    )

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
        logger.warning(
            f"[update_creds_for_org] Credentials not found | {{'org_id': {org_id}, 'provider': '{creds_in.provider}', 'project_id': {creds_in.project_id}}}"
        )
        logger.error(
            f"[update_creds_for_org] Update failed: Credentials not found | {{'org_id': {org_id}, 'provider': '{creds_in.provider}'}}"
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
        f"[update_creds_for_org] Credentials updated successfully | {{'org_id': {org_id}, 'provider': '{creds_in.provider}', 'credential_id': {creds.id}}}"
    )

    return [creds]


def remove_provider_credential(
    session: Session, org_id: int, provider: str, project_id: Optional[int] = None
) -> Credential:
    """Remove credentials for a specific provider."""
    logger.info(
        f"[remove_provider_credential] Starting credential removal | {{'org_id': {org_id}, 'provider': '{provider}', 'project_id': {project_id}}}"
    )
    validate_provider(provider)

    statement = select(Credential).where(
        Credential.organization_id == org_id,
        Credential.provider == provider,
        Credential.project_id == project_id if project_id is not None else True,
    )
    creds = session.exec(statement).first()

    if not creds:
        logger.warning(
            f"[remove_provider_credential] Credentials not found | {{'org_id': {org_id}, 'provider': '{provider}', 'project_id': {project_id}}}"
        )
        raise HTTPException(
            status_code=404, detail="Credentials not found for this provider"
        )

    # Soft delete
    creds.is_active = False
    creds.updated_at = now()
    session.add(creds)
    session.commit()
    session.refresh(creds)
    logger.info(
        f"[remove_provider_credential] Credentials removed successfully | {{'org_id': {org_id}, 'provider': '{provider}', 'credential_id': {creds.id}}}"
    )

    return creds


def remove_creds_for_org(
    *, session: Session, org_id: int, project_id: Optional[int] = None
) -> List[Credential]:
    """Removes all credentials for an organization."""
    logger.info(
        f"[remove_creds_for_org] Starting removal of all credentials | {{'org_id': {org_id}, 'project_id': {project_id}}}"
    )
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
        logger.info(
            f"[remove_creds_for_org] Credential deactivated | {{'org_id': {org_id}, 'provider': '{cred.provider}', 'credential_id': {cred.id}}}"
        )

    session.commit()
    logger.info(
        f"[remove_creds_for_org] All credentials removed successfully | {{'org_id': {org_id}, 'credential_count': {len(creds)}}}"
    )
    return creds
