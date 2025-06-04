from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Optional
from langfuse.client import Langfuse
from pydantic import BaseModel

from app.api.deps import get_current_user_org, get_db
from app.crud.credentials import get_provider_credential
from app.models import UserOrganization
from app.utils import APIResponse

router = APIRouter(prefix="/prompts", tags=["prompts"])

class PromptCreateRequest(BaseModel):
    project_id: int
    name: str
    type: str
    prompt: str
    version: int
    labels: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    supported_languages: Optional[List[str]] = None

class PromptGetRequest(BaseModel):
    project_id: int
    name: str
    type: Optional[str] = None
    version: Optional[int] = None
    labels: Optional[List[str]] = None
    tags: Optional[List[str]] = None

class PromptUpdateRequest(BaseModel):
    project_id: int
    name: str
    type: Optional[str] = None
    prompt: Optional[str] = None
    labels: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    supported_languages: Optional[List[str]] = None

def initialize_langfuse(
    project_id: int,
    _session: Session,
    _current_user: UserOrganization,
):
    langfuse_credentials = get_provider_credential(
        session=_session,
        org_id=_current_user.organization_id,
        provider="langfuse",
        project_id=project_id,
    )
    if not langfuse_credentials or "api_key" not in langfuse_credentials:
        raise HTTPException(status_code=400, detail="Langfuse API key not configured for this organization.")
    return Langfuse(api_key=langfuse_credentials["api_key"])

@router.post("/", response_model=APIResponse[dict])
def create_new_prompt(
    request: PromptCreateRequest,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org)
):
    langfuse_client = initialize_langfuse(request.project_id, _session, _current_user)
    langfuse_client.create_prompt(
        name=request.name,
        type=request.type,
        prompt=request.prompt,
        labels=request.labels,
        tags=request.tags,
        config={
            "model": request.model,
            "temperature": request.temperature,
            "supported_languages": request.supported_languages,
        },
    )
    return APIResponse.success_response(
        message="Prompt created successfully",
        data=request.dict(),
    )

@router.get("/")
def get_prompt(
    request: PromptGetRequest,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org)
):
    langfuse_client = initialize_langfuse(request.project_id, _session, _current_user)
    prompt = langfuse_client.get_prompt(request.name, request.type, request.version)
    return APIResponse.success_response(
        message="Prompt fetched successfully",
        data=prompt,
    )

@router.put("/")
def update_prompt(
    request: PromptUpdateRequest,
    _session: Session = Depends(get_db),
    _current_user: UserOrganization = Depends(get_current_user_org)
):
    langfuse_client = initialize_langfuse(request.project_id, _session, _current_user)
    langfuse_client.update_prompt(
        request.name,
        request.type,
        request.version,
        request.prompt,
        request.labels,
    )
    return APIResponse.success_response(
        message="Prompt updated successfully",
        data=request.dict(),
    )