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
from app.crud.credentials import set_creds_for_org, get_key_by_org, remove_creds_for_org, get_creds_by_org, update_creds_for_org
from app.utils import APIResponse 

router = APIRouter(prefix="/credentials", tags=["credentials"])

@router.post("/", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[CredsPublic])
def create_new_credential(*, session: SessionDep, creds_in: CredsCreate):
    try:
        existing_creds = get_creds_by_org(session=session, org_id=creds_in.organization_id)

        if existing_creds:
            raise HTTPException(status_code=400, detail="Credentials for this organization already exist.")
        
        new_creds = set_creds_for_org(session=session, creds_add=creds_in)
        return APIResponse.success_response(new_creds)
    
    except HTTPException as http_error:
        raise http_error
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[CredsPublic])
def read_credential(*, session: SessionDep, org_id: int):
    try:
        creds = get_creds_by_org(session=session, org_id=org_id)
        if creds is None:
            raise HTTPException(status_code=404, detail="Credentials not found")
        return APIResponse.success_response(creds)
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/{org_id}/api-key", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[dict])
def read_api_key(*, session: SessionDep, org_id: int):
    try:
        api_key = get_key_by_org(session=session, org_id=org_id)
        if api_key is None:
            raise HTTPException(status_code=404, detail="API key not found")
        
        return APIResponse.success_response({"api_key": api_key})
    
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    
@router.patch("/{org_id}", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[CredsPublic])
def update_credential(*, session: SessionDep, org_id: int, creds_in: CredsUpdate):
    try:
        updated_creds = update_creds_for_org(session=session, org_id=org_id, creds_in=creds_in)
        return APIResponse.success_response(updated_creds)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{org_id}/api-key", dependencies=[Depends(get_current_active_superuser)], response_model=APIResponse[dict])
def delete_credential(*, session: SessionDep, org_id: int):
    try:
        creds = remove_creds_for_org(session=session, org_id=org_id)
        
        if creds is None:
            raise HTTPException(status_code=404, detail="Credentials not found")
        
        return APIResponse.success_response({"message": "Credentials deleted successfully"})
    
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")