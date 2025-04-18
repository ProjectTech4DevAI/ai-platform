from typing import Optional, Dict, Any
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.models import Credential, CredsCreate, CredsUpdate


def set_creds_for_org(*, session: Session, creds_add: CredsCreate) -> Credential:
    creds = Credential.model_validate(creds_add)

    # Set the inserted_at timestamp (current UTC time)
    creds.inserted_at = datetime.utcnow()

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
    # Fetch the current credentials for the organization
    creds = session.exec(
        select(Credential).where(Credential.organization_id == org_id)
    ).first()

    if not creds:
        raise ValueError(f"Credentials not found")

    # Update the credentials data with the provided values
    creds_data = creds_in.dict(exclude_unset=True)

    # Directly update the fields on the original creds object instead of creating a new one
    for key, value in creds_data.items():
        setattr(creds, key, value)

    # Set the updated_at timestamp (current UTC time)
    creds.updated_at = datetime.utcnow()

    try:
        # Add the updated creds to the session and flush the changes to the database
        session.add(creds)
        session.flush()  # This will flush the changes to the database but without committing
        session.commit()  # Now we commit the changes to make them permanent
    except IntegrityError as e:
        # Rollback in case of any integrity errors (e.g., constraint violations)
        session.rollback()
        raise ValueError(f"Error while updating credentials: {str(e)}")

    # Refresh the session to get the latest updated data
    session.refresh(creds)

    return creds


def remove_creds_for_org(*, session: Session, org_id: int) -> Optional[Credential]:
    """Removes (soft deletes) the credentials for the given organization."""
    statement = select(Credential).where(Credential.organization_id == org_id)
    creds = session.exec(statement).first()

    if creds:
        try:
            # Soft delete: Set is_active to False and set deleted_at timestamp
            creds.is_active = False
            creds.deleted_at = (
                datetime.utcnow()
            )  # Set the current time as the deleted_at timestamp
            session.add(creds)
            session.commit()
        except IntegrityError as e:
            session.rollback()  # Rollback in case of a failure during delete operation
            raise ValueError(f"Error while deleting credentials: {str(e)}")

    return creds
