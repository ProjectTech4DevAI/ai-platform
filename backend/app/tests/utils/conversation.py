from uuid import uuid4
from sqlmodel import Session, select

from app.models import OpenAIConversation, OpenAIConversationCreate
from app.crud.openai_conversation import create_conversation


def get_conversation(
    session: Session, response_id: str | None = None, project_id: int | None = None
) -> OpenAIConversation:
    """
    Retrieve an active conversation from the database.

    If a response_id is provided, fetch the active conversation with that response_id.
    If a project_id is provided, fetch a conversation from that specific project.
    If no response_id or project_id is provided, fetch any random conversation.
    """
    if response_id:
        statement = (
            select(OpenAIConversation)
            .where(
                OpenAIConversation.response_id == response_id,
                OpenAIConversation.is_deleted == False,
            )
            .limit(1)
        )
    elif project_id:
        statement = (
            select(OpenAIConversation)
            .where(
                OpenAIConversation.project_id == project_id,
                OpenAIConversation.is_deleted == False,
            )
            .limit(1)
        )
    else:
        statement = (
            select(OpenAIConversation)
            .where(OpenAIConversation.is_deleted == False)
            .limit(1)
        )

    conversation = session.exec(statement).first()

    if not conversation:
        # Create a new conversation if none exists
        from app.tests.utils.utils import get_project, get_organization

        if project_id:
            # Get the specific project
            from app.models import Project

            project = session.exec(
                select(Project).where(Project.id == project_id)
            ).first()
            if not project:
                raise ValueError(f"Project with ID {project_id} not found")
        else:
            project = get_project(session)

        organization = get_organization(session)

        conversation_data = OpenAIConversationCreate(
            response_id=f"resp_{uuid4()}",
            ancestor_response_id=None,
            previous_response_id=None,
            user_question="Test question",
            response="Test response",
            model="gpt-4o",
            assistant_id=f"asst_{uuid4()}",
        )

        conversation = create_conversation(
            session=session,
            conversation=conversation_data,
            project_id=project.id,
            organization_id=organization.id,
        )

    return conversation
