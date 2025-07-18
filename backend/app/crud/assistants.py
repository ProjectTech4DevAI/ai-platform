import logging

from typing import Optional
import uuid

import openai
from fastapi import HTTPException
from openai import OpenAI
from openai.types.beta import Assistant as OpenAIAssistant
from sqlmodel import Session, and_, select

from app.models import Assistant, AssistantCreate
from app.utils import mask_string

logger = logging.getLogger(__name__)


def get_assistant_by_id(
    session: Session, assistant_id: str, project_id: int
) -> Optional[Assistant]:
    """Get an assistant by its OpenAI assistant ID and organization ID."""
    statement = select(Assistant).where(
        and_(
            Assistant.assistant_id == assistant_id,
            Assistant.project_id == project_id,
        )
    )
    return session.exec(statement).first()


def fetch_assistant_from_openai(assistant_id: str, client: OpenAI) -> OpenAIAssistant:
    """
    Fetch an assistant from OpenAI.
    Returns OpenAI Assistant model.
    """

    try:
        assistant = client.beta.assistants.retrieve(assistant_id=assistant_id)
        return assistant
    except openai.NotFoundError as e:
        logger.error(
            f"[fetch_assistant_from_openai] Assistant not found: {mask_string(assistant_id)} | {e}"
        )
        raise HTTPException(status_code=404, detail="Assistant not found in OpenAI.")
    except openai.OpenAIError as e:
        logger.error(
            f"[fetch_assistant_from_openai] OpenAI API error while retrieving assistant {mask_string(assistant_id)}: {e}"
        )
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {e}")


def verify_vector_store_ids_exist(openai_client: OpenAI, vector_store_ids: list[str]) -> None:
    """
    Raises HTTPException if any of the vector_store_ids do not exist in OpenAI.
    """
    for vs_id in vector_store_ids:
        try:
            openai_client.vector_stores.retrieve(vs_id)
        except Exception as e:
            logger.error(f"Vector store id {vs_id} not found in OpenAI: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Vector store ID {vs_id} not found in OpenAI."
            )


def sync_assistant(
    session: Session,
    organization_id: int,
    project_id: int,
    openai_assistant: OpenAIAssistant,
) -> Assistant:
    """
    Insert an assistant into the database by converting OpenAI Assistant to local Assistant model.
    """
    assistant_id = openai_assistant.id

    existing_assistant = get_assistant_by_id(session, assistant_id, project_id)
    if existing_assistant:
        logger.info(
            f"[sync_assistant] Assistant with ID {mask_string(assistant_id)} already exists in the database."
        )
        raise HTTPException(
            status_code=409,
            detail=f"Assistant with ID {assistant_id} already exists.",
        )

    if not openai_assistant.instructions:
        raise HTTPException(
            status_code=400,
            detail="Assistant has no instruction.",
        )

    vector_store_ids = []
    if openai_assistant.tool_resources and hasattr(
        openai_assistant.tool_resources, "file_search"
    ):
        file_search = openai_assistant.tool_resources.file_search
        if file_search and hasattr(file_search, "vector_store_ids"):
            vector_store_ids = file_search.vector_store_ids or []

    max_num_results = 20
    for tool in openai_assistant.tools or []:
        if tool.type == "file_search":
            file_search = getattr(tool, "file_search", None)
            if file_search and hasattr(file_search, "max_num_results"):
                max_num_results = file_search.max_num_results
            break

    db_assistant = Assistant(
        assistant_id=openai_assistant.id,
        name=openai_assistant.name or openai_assistant.id,
        instructions=openai_assistant.instructions,
        model=openai_assistant.model,
        vector_store_ids=vector_store_ids,
        temperature=openai_assistant.temperature or 0.1,
        max_num_results=max_num_results,
        project_id=project_id,
        organization_id=organization_id,
    )

    session.add(db_assistant)
    session.commit()
    session.refresh(db_assistant)

    logger.info(
        f"[sync_assistant] Successfully ingested assistant with ID {mask_string(assistant_id)}."
    )
    return db_assistant


def create_assistant(
    session: Session,
    openai_client: OpenAI,
    assistant: AssistantCreate,
    project_id: int,
    organization_id: int,
) -> Assistant:
    
    verify_vector_store_ids_exist(openai_client, assistant.vector_store_ids)
    
    assistant = Assistant(
        assistant_id= uuid.uuid4(),
        **assistant.model_dump(),
        project_id=project_id,
        organization_id=organization_id,
    )
    session.add(assistant)
    session.commit()
    session.refresh(assistant)
    return assistant