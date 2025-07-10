import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlmodel import Session
import openai
from openai import OpenAI

from app.api.deps import get_db, get_current_user_org_project
from app.crud import get_assistant_by_id, get_provider_credential
from app.models import Assistant, UserProjectOrg
from app.utils import APIResponse, mask_string

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["Assistants"])


def handle_openai_error(e: openai.OpenAIError) -> str:
    """Extract error message from OpenAI error."""
    if isinstance(e.body, dict) and "message" in e.body:
        return e.body["message"]
    return str(e)


@router.post(
    "/{assistant_id}/ingest",
    response_model=APIResponse[Assistant],
    status_code=status.HTTP_201_CREATED,
)
def ingest_assistant(
    assistant_id: Annotated[str, Path(description="The ID of the assistant to ingest")],
    session: Session = Depends(get_db),
    current_user: UserProjectOrg = Depends(get_current_user_org_project),
):
    """
    Ingest a assistant from OpenAI and store it in the platform.
    """

    existing_assistant = get_assistant_by_id(
        session, assistant_id, current_user.organization_id
    )
    if existing_assistant:
        logger.info(f"Assistant with ID {assistant_id} already exists in the database.")
        metadata = {"message": f"Assistant with ID {assistant_id} already exists."}
        return APIResponse(success=True, metadata=metadata, data=existing_assistant)

    credentials = get_provider_credential(
        session=session,
        org_id=current_user.organization_id,
        provider="openai",
        project_id=current_user.project_id,
    )

    if not credentials or "api_key" not in credentials:
        logger.error(
            f"OpenAI API key not configured for org_id={current_user.organization_id}, project_id={current_user.project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key not configured for this organization or project.",
        )

    client = OpenAI(api_key=credentials["api_key"])

    try:
        assistant = client.beta.assistants.retrieve(assistant_id=assistant_id)
    except openai.OpenAIError as e:
        error_msg = handle_openai_error(e)
        logger.error(
            f"OpenAI API error while retrieving assistant {mask_string(assistant_id)}: {error_msg}"
        )
        raise HTTPException(status_code=400, detail=f"OpenAI API error: {error_msg}")

    vector_store_ids = []
    if assistant.tool_resources and hasattr(assistant.tool_resources, "file_search"):
        file_search = assistant.tool_resources.file_search
        if file_search and hasattr(file_search, "vector_store_ids"):
            vector_store_ids = file_search.vector_store_ids or []

    max_num_results = 20
    for tool in assistant.tools or []:
        if tool.type == "file_search":
            file_search = getattr(tool, "file_search", None)
            if file_search and hasattr(file_search, "max_num_results"):
                max_num_results = file_search.max_num_results
            break

    if not assistant.instructions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assistant has no instruction.",
        )

    db_assistant = Assistant(
        assistant_id=assistant.id,
        name=assistant.name or assistant.id,
        instructions=assistant.instructions,
        model=assistant.model,
        vector_store_ids=vector_store_ids,
        temperature=assistant.temperature or 0.1,
        max_num_results=max_num_results,
        project_id=current_user.project_id,
        organization_id=current_user.organization_id,
    )

    session.add(db_assistant)
    session.commit()
    session.refresh(db_assistant)

    logger.info(f"Successfully ingested assistant with ID {mask_string(assistant_id)}.")
    return APIResponse(
        success=True,
        message=f"Assistant with ID {assistant_id} ingested successfully.",
        data=db_assistant,
    )
