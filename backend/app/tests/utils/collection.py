from uuid import UUID
from uuid import uuid4

from openai import OpenAI
from sqlmodel import Session

from app.core.config import settings
from app.models import Collection, Organization, Project
from app.tests.utils.utils import get_user_id_by_email, get_project
from app.tests.utils.test_data import create_test_project
from app.tests.utils.test_data import create_test_api_key


class constants:
    openai_model = "gpt-4o"
    llm_service_name = "test-service-name"


def uuid_increment(value: UUID):
    inc = int(value) + 1  # hopefully doesn't overflow!
    return UUID(int=inc)


def get_collection(db: Session, client=None, project_id: int = None) -> Collection:
    project = get_project(db)
    if client is None:
        client = OpenAI(api_key="test_api_key")

    vector_store = client.vector_stores.create()
    assistant = client.beta.assistants.create(
        model=constants.openai_model,
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    return Collection(
        organization_id=project.organization_id,
        project_id=project_id,
        llm_service_id=assistant.id,
        llm_service_name=constants.llm_service_name,
    )
