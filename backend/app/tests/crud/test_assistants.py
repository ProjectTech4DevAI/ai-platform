import pytest
from sqlmodel import Session
from fastapi import HTTPException

from app.tests.utils.openai import mock_openai_assistant
from app.tests.utils.utils import get_project
from app.crud.assistants import sync_assistant


class TestAssistant:
    def test_sync_assistant_success(self, db: Session):
        project = get_project(db)
        openai_assistant = mock_openai_assistant(
            assistant_id="asst_success",
            vector_store_ids=["vs_1", "vs_2"],
            max_num_results=20,
        )

        result = sync_assistant(
            db, project.organization_id, project.id, openai_assistant
        )

        assert result.assistant_id == openai_assistant.id
        assert result.project_id == project.id
        assert result.organization_id == project.organization_id
        assert result.name == openai_assistant.name
        assert result.instructions == openai_assistant.instructions
        assert result.model == openai_assistant.model
        assert result.vector_store_ids == ["vs_1", "vs_2"]
        assert result.temperature == openai_assistant.temperature
        assert result.max_num_results == 20

    def test_sync_assistant_already_exists(self, db: Session):
        project = get_project(db)
        openai_assistant = mock_openai_assistant(
            assistant_id="asst_exists",
        )

        sync_assistant(db, project.organization_id, project.id, openai_assistant)

        with pytest.raises(HTTPException) as exc_info:
            sync_assistant(db, project.organization_id, project.id, openai_assistant)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail

    def test_sync_assistant_no_instructions(self, db: Session):
        project = get_project(db)
        openai_assistant = mock_openai_assistant(
            assistant_id="asst_no_instructions",
        )
        openai_assistant.instructions = None

        with pytest.raises(HTTPException) as exc_info:
            sync_assistant(db, project.organization_id, project.id, openai_assistant)

        assert exc_info.value.status_code == 400
        assert "no instruction" in exc_info.value.detail

    def test_sync_assistant_no_name(self, db: Session):
        project = get_project(db)
        openai_assistant = mock_openai_assistant(
            assistant_id="asst_no_name",
        )
        openai_assistant.name = None

        result = sync_assistant(
            db, project.organization_id, project.id, openai_assistant
        )

        assert result.name == openai_assistant.id
        assert result.assistant_id == openai_assistant.id
        assert result.project_id == project.id

    def test_sync_assistant_no_vector_stores(self, db: Session):
        project = get_project(db)
        openai_assistant = mock_openai_assistant(
            assistant_id="asst_no_vectors", vector_store_ids=None
        )

        result = sync_assistant(
            db, project.organization_id, project.id, openai_assistant
        )

        assert result.vector_store_ids == []
        assert result.assistant_id == openai_assistant.id
        assert result.project_id == project.id

    def test_sync_assistant_no_tools(self, db: Session):
        project = get_project(db)
        openai_assistant = mock_openai_assistant(assistant_id="asst_no_tools")

        openai_assistant.tool_resources = None
        result = sync_assistant(
            db, project.organization_id, project.id, openai_assistant
        )

        assert result.vector_store_ids == []  # Default value
        assert result.assistant_id == openai_assistant.id
        assert result.project_id == project.id

    def test_sync_assistant_no_tool_resources(self, db: Session):
        project = get_project(db)
        openai_assistant = mock_openai_assistant(
            assistant_id="asst_no_tool_resources",
        )
        openai_assistant.tools = None

        result = sync_assistant(
            db, project.organization_id, project.id, openai_assistant
        )

        assert result.max_num_results == 20
        assert result.assistant_id == openai_assistant.id
        assert result.project_id == project.id
