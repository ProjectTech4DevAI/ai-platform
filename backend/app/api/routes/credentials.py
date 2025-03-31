from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Creds, CredsCreate, CredsUpdate, CredsPublic
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.crud.credentials import set_creds_for_org, get_key_by_org, remove_creds_for_org, get_creds_by_org
from app.utils import APIResponse 

router = APIRouter(prefix="/credentials", tags=["credentials"])

@router.post("/", response_model=APIResponse[CredsPublic])
def create_new_credential(*, session: SessionDep, creds_in: CredsCreate):
    new_creds = set_creds_for_org(session=session, creds_add=creds_in)
    return APIResponse.success_response(new_creds)


@router.get("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[CredsPublic])
def read_credential(*, session: SessionDep, org_id: int):
    creds = get_creds_by_org(session=session, org_id=org_id)
    if creds is None:
        raise HTTPException(status_code=404, detail="Credentials not found")
    return APIResponse.success_response(creds)

@router.get("/{org_id}/api-key", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[str])
def read_api_key(*, session: SessionDep, org_id: int):
    api_key = get_key_by_org(session=session, org_id=org_id)
    
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    
    return APIResponse.success_response(api_key)

@router.patch("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[CredsPublic])
def update_credential(*, session: SessionDep, org_id: int, creds_in: CredsUpdate):
    creds = get_creds_by_org(session=session, org_id=org_id)
    if creds is None:
        raise HTTPException(status_code=404, detail="Credentials not found")

    # Update only the fields that were provided in the request
    creds_data = creds_in.dict(exclude_unset=True)  # Exclude unset fields
    creds = creds.model_copy(update=creds_data)

    session.add(creds)
    session.commit()
    session.flush(creds)

    return APIResponse.success_response(creds)


@router.delete("/{org_id}/api-key", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[None])
def delete_credential(*, session: SessionDep, org_id: int):
    creds = remove_creds_for_org(session=session, org_id=org_id)
    if creds is None:
        raise HTTPException(status_code=404, detail="API key for organization not found")
    return APIResponse.success_response(None)
