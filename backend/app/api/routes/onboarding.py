from fastapi import APIRouter, Depends

from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
)
from app.crud import onboard_project
from app.models import OnboardingRequest, OnboardingResponse, User
from app.utils import APIResponse, load_description

router = APIRouter(tags=["Onboarding"])


@router.post(
    "/onboard",
    response_model=APIResponse[OnboardingResponse],
    status_code=201,
    description=load_description("onboarding/onboarding.md"),
)
def onboard_project_route(
    onboard_in: OnboardingRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
):
    response = onboard_project(session=session, onboard_in=onboard_in)

    metadata = None
    if onboard_in.credentials:
        metadata = {"note": ("Given credential(s) have been saved for this project.")}

    return APIResponse.success_response(data=response, metadata=metadata)
