from typing import Optional, Dict, Any

from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.models import Credential, CredsCreate, CredsUpdate


def set_creds_for_org(*, session: Session, creds_add: CredsCreate) -> Credential:
    creds = Credential.model_validate(creds_add)

    try:
        session.add(creds)
        session.commit()
        session.refresh(creds)
    except IntegrityError as e:
        session.rollback()  # Rollback the session if there's a unique constraint violation
        raise ValueError(f"Error while adding credentials: {str(e)}")

    return creds


def get_creds_by_org(*, session: Session, org_id: int) -> Optional[Credential]:
    """Fetches the credentials for the given organization."""
    statement = select(Credential).where(Credential.organization_id == org_id)
    return session.exec(statement).first()


def get_key_by_org(*, session: Session, org_id: int) -> Optional[str]:
    """Fetches the API key from the credentials for the given organization."""
    statement = select(Credential).where(Credential.organization_id == org_id)
    creds = session.exec(statement).first()

    # Check if creds exists and if the credential field contains the api_key
    if (
        creds
        and creds.credential
        and "openai" in creds.credential
        and "api_key" in creds.credential["openai"]
    ):
        return creds.credential["openai"]["api_key"]

    return None


def update_creds_for_org(
    session: Session, org_id: int, creds_in: CredsUpdate
) -> Credential:
    creds = session.exec(
        select(Credential).where(Credential.organization_id == org_id)
    ).first()

    if not creds:
        raise ValueError(f"Credentials not found")

    creds_data = creds_in.dict(exclude_unset=True)
    updated_creds = creds.model_copy(update=creds_data)

    try:
        session.add(updated_creds)
        session.commit()
    except IntegrityError as e:
        session.rollback()  # Rollback the session if there's a constraint violation
        raise ValueError(f"Error while updating credentials: {str(e)}")

    session.refresh(updated_creds)  # Refresh to get the updated values

    return updated_creds


def remove_creds_for_org(*, session: Session, org_id: int) -> Optional[Credential]:
    """Removes the credentials for the given organization."""
    statement = select(Credential).where(Credential.organization_id == org_id)
    creds = session.exec(statement).first()

    if creds:
        try:
            session.delete(creds)
            session.commit()
        except IntegrityError as e:
            session.rollback()  # Rollback in case of a failure during delete operation
            raise ValueError(f"Error while deleting credentials: {str(e)}")

    return creds
