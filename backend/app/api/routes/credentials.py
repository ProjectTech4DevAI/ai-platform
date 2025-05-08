from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import SessionDep, get_current_active_superuser
from app.crud.credentials import (
    get_creds_by_org,
    get_key_by_org,
    remove_creds_for_org,
    set_creds_for_org,
    update_creds_for_org,
)
from app.models import CredsCreate, CredsPublic, CredsUpdate
from app.utils import APIResponse
from datetime import datetime

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[CredsPublic],
)
def create_new_credential(*, session: SessionDep, creds_in: CredsCreate):
    new_creds = None
    try:
        existing_creds = get_creds_by_org(
            session=session, org_id=creds_in.organization_id
        )
        if not existing_creds:
            new_creds = set_creds_for_org(session=session, creds_add=creds_in)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

    # Ensure inserted_at is set during creation
    new_creds.inserted_at = datetime.utcnow()

    return APIResponse.success_response(new_creds)


@router.get(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[CredsPublic],
)
def read_credential(*, session: SessionDep, org_id: int):
    try:
        creds = get_creds_by_org(session=session, org_id=org_id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

    if creds is None:
        raise HTTPException(status_code=404, detail="Credentials not found")

    return APIResponse.success_response(creds)


@router.get(
    "/{org_id}/api-key",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[dict],
    include_in_schema=False,
)
def read_api_key(*, session: SessionDep, org_id: int):
    try:
        api_key = get_key_by_org(session=session, org_id=org_id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    return APIResponse.success_response({"api_key": api_key})


@router.patch(
    "/{org_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[CredsPublic],
)
def update_credential(*, session: SessionDep, org_id: int, creds_in: CredsUpdate):
    try:
        updated_creds = update_creds_for_org(
            session=session, org_id=org_id, creds_in=creds_in
        )

        updated_creds.updated_at = datetime.utcnow()

        return APIResponse.success_response(updated_creds)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


from fastapi import HTTPException, Depends
from app.crud.credentials import remove_creds_for_org
from app.utils import APIResponse
from app.api.deps import SessionDep, get_current_active_superuser


@router.delete(
    "/{org_id}/api-key",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[dict],
)
def delete_credential(*, session: SessionDep, org_id: int):
    try:
        creds = remove_creds_for_org(session=session, org_id=org_id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

    if creds is None:
        raise HTTPException(
            status_code=404, detail="Credentials for organization not found"
        )

    # No need to manually set deleted_at and is_active if it's done in remove_creds_for_org
    # Simply return the success response
    return APIResponse.success_response({"message": "Credentials deleted successfully"})
