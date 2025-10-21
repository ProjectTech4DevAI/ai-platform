import logging

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import AuthContext, SessionDep
from app.models.llm import LLMCallRequest
from app.services.llm.jobs import start_job
from app.utils import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["llm"])


@router.post("/llm/call")
async def llm_call(
    request: LLMCallRequest,
    _session: SessionDep,
    _current_user: AuthContext
):
    """
    Endpoint to initiate an LLM call as a background job.
    """
    project_id = _current_user.project.id
    organization_id = _current_user.organization.id

    logger.info(
        f"[llm_call] Scheduling LLM call for provider: {request.llm.llm_model_spec.provider}, "
        f"model: {request.llm.llm_model_spec.model}, "
        f"project_id: {project_id}, org_id: {organization_id}"
    )

    # Start background job
    job_id = start_job(
        db=_session,
        request=request,
        project_id=project_id,
        organization_id=organization_id,
    )

    logger.info(
        f"[llm_call] LLM call job scheduled successfully | job_id={job_id}, "
        f"project_id={project_id}"
    )

    return APIResponse.success_response(
        data={"status": "processing", "message": "LLM call job scheduled"},
    )
