from typing import Optional, Dict, Any

from sqlmodel import Session, select

from app.models import Creds, CredsCreate

def set_creds_for_org(*, session: Session, creds_add: CredsCreate) -> Creds:
    """Sets or updates the credentials for the given organization."""
    statement = select(Creds).where(Creds.organization_id == creds_add.organization_id)
    creds = session.exec(statement).first()

    # If the organization already has credentials
    if creds:
        creds.credential = creds_add.credential  # Update the credential field (the JSON field)
        creds.is_active = True
        creds.valid = True
        session.add(creds)
    else:
        # Create new Creds record using the validated data
        creds = Creds.model_validate(creds_add)
        session.add(creds)

    session.commit()
    session.refresh(creds)
    return creds


def get_creds_by_org(*, session: Session, org_id: int) -> Optional[Creds]:
    """Fetches the credentials for the given organization."""
    statement = select(Creds).where(Creds.organization_id == org_id)
    return session.exec(statement).first()

def get_key_by_org(*, session: Session, org_id: int) -> Optional[str]:
    """Fetches the API key from the credentials for the given organization."""
    statement = select(Creds).where(Creds.organization_id == org_id)
    creds = session.exec(statement).first()
    
    # Check if creds exists and if the credential field contains the api_key
    if creds and creds.credential and "openai" in creds.credential and "api_key" in creds.credential["openai"]:
        return creds.credential["openai"]["api_key"]
    
    return None

def remove_creds_for_org(*, session: Session, org_id: int) -> Optional[Creds]:
    """Removes the credentials for the given organization."""
    statement = select(Creds).where(Creds.organization_id == org_id)
    creds = session.exec(statement).first()
    
    if creds:
        session.delete(creds)
        session.commit()
    
    return creds  # Return the deleted Creds or None if not found
