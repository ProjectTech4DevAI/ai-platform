from app.models import Collection
from app.tests.utils.utils import get_user_id_by_email


class constants:
    openai_model = "gpt-4o"
    openai_mock_key = "sk-fake123"
    llm_service_name = "test-service-name"


def get_collection(db, client):
    owner_id = get_user_id_by_email(db)

    vector_store = client.vector_stores.create()
    assistant = client.beta.assistants.create(
        model=constants.openai_model,
        tools=[
            {
                "type": "file_search",
            },
        ],
        tool_resources={
            "file_search": {
                "vector_store_ids": [
                    vector_store.id,
                ],
            },
        },
    )

    return Collection(
        owner_id=owner_id,
        llm_service_id=assistant.id,
        llm_service_name=constants.llm_service_name,
    )
