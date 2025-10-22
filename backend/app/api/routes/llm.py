import logging

from fastapi import APIRouter

from app.api.deps import AuthContextDep, SessionDep
from app.models.llm import LLMCallRequest
from app.services.llm.jobs import start_job
from app.utils import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["LLM"])


@router.post("/llm/call")
async def llm_call(
    _current_user: AuthContextDep, _session: SessionDep, request: LLMCallRequest
):
    """
    Endpoint to initiate an LLM call as a background job.
    """
    project_id = _current_user.project.id
    organization_id = _current_user.organization.id

    # Start background job
    job_id = start_job(
        db=_session,
        request=request,
        project_id=project_id,
        organization_id=organization_id,
    )

    return APIResponse.success_response(
        data={"status": "processing", "message": "LLM call job scheduled"},
    )
