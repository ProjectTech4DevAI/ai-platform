from unittest.mock import patch, MagicMock
from uuid import uuid4
from dataclasses import asdict

from sqlmodel import Session
from sqlalchemy.exc import SQLAlchemyError


from app.models.collection import (
    DeletionRequest,
    Collection,
    ResponsePayload,
)
from app.tests.utils.utils import get_project
from app.crud import CollectionCrud
from app.crud import CollectionCrud, CollectionJobCrud
from app.models import CollectionJobStatus, CollectionJob
from app.tests.utils.utils import get_project
from app.services.collections.delete_collection import start_job, execute_job


def create_collection(db: Session, project):
    collection = Collection(
        id=uuid4(),
        project_id=project.id,
        organization_id=project.organization_id,
        llm_service_id="asst-nasjnl",
    )
    collection = CollectionCrud(db, project.id).create(collection)
    return collection


def create_collection_job(db: Session, project, collection):
    job_id = uuid4()
    job_crud = CollectionJobCrud(db, project.id)
    job = job_crud.create(
        CollectionJob(
            id=job_id,
            action_type="delete",
            project_id=project.id,
            collection_id=collection.id,
            status=CollectionJobStatus.processing,
        )
    )
    return job


def test_start_job_creates_collection_job_and_schedules_task(db: Session):
    """
    - start_job should create a CollectionJob (status=processing, action=delete)
    - schedule the task with a *generated* job_id and the provided collection_id
    - return the collection.id (per implementation)
    """
    project = get_project(db)

    created_collection = create_collection(db, project)

    req = DeletionRequest(collection_id=created_collection.id)
    payload = {"status": "processing"}

    with patch(
        "app.services.collections.delete_collection.start_low_priority_job"
    ) as mock_schedule:
        mock_schedule.return_value = "fake-task-id"

        returned = start_job(
            db=db,
            request=req.model_dump(),
            collection=created_collection,
            project_id=project.id,
            payload=payload,
            organization_id=project.organization_id,
        )

        assert returned == created_collection.id

        jobs = CollectionJobCrud(db, project.id).read_all()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.project_id == project.id
        assert job.collection_id == created_collection.id
        assert job.status == CollectionJobStatus.processing
        assert job.action_type == "delete"

        mock_schedule.assert_called_once()
        kwargs = mock_schedule.call_args.kwargs
        assert (
            kwargs["function_path"]
            == "app.services.collections.delete_collection.execute_job"
        )
        assert kwargs["project_id"] == project.id
        assert kwargs["organization_id"] == project.organization_id
        assert kwargs["job_id"] == job.id
        assert kwargs["collection_id"] == created_collection.id
        assert kwargs["request"] == req.model_dump()
        assert kwargs["payload_data"] == payload
        assert "trace_id" in kwargs


@patch("app.services.collections.delete_collection.get_openai_client")
def test_execute_job_delete_success_updates_job_and_calls_delete(
    mock_get_openai_client, db: Session
):
    """
    - execute_job should set task_id on the CollectionJob
    - call CollectionCrud.delete(collection, assistant_crud)
    - mark job successful and clear error_message
    """
    project = get_project(db)

    collection = create_collection(db, project)

    job = create_collection_job(db, project, collection)

    mock_get_openai_client.return_value = MagicMock()

    with patch(
        "app.services.collections.delete_collection.Session"
    ) as SessionCtor, patch(
        "app.services.collections.delete_collection.OpenAIAssistantCrud"
    ) as MockAssistantCrud, patch(
        "app.services.collections.delete_collection.CollectionCrud"
    ) as MockCollectionCrud:
        SessionCtor.return_value.__enter__.return_value = db
        SessionCtor.return_value.__exit__.return_value = False

        collection_crud_instance = MockCollectionCrud.return_value
        collection_crud_instance.read_one.return_value = collection

        deletion_result = MagicMock()
        deletion_result.model_dump.return_value = {
            "id": str(collection.id),
            "deleted": True,
        }
        collection_crud_instance.delete.return_value = deletion_result

        task_id = uuid4()
        req = DeletionRequest(collection_id=collection.id)
        payload = ResponsePayload(status="processing", route="/test/delete")

        execute_job(
            request=req.model_dump(),
            payload_data=asdict(payload),
            project_id=project.id,
            organization_id=project.organization_id,
            task_id=task_id,
            job_id=job.id,
            collection_id=collection.id,
            task_instance=None,
        )

        updated_job = CollectionJobCrud(db, project.id).read_one(job.id)
        assert updated_job.task_id == task_id
        assert updated_job.status == CollectionJobStatus.successful
        assert updated_job.error_message in (None, "")

        MockCollectionCrud.assert_called_with(db, project.id)
        collection_crud_instance.read_one.assert_called_once_with(collection.id)
        collection_crud_instance.delete.assert_called_once()
        args, kwargs = collection_crud_instance.delete.call_args
        assert isinstance(args[0], Collection)
        MockAssistantCrud.assert_called_once()
        mock_get_openai_client.assert_called_once()


@patch("app.services.collections.delete_collection.get_openai_client")
def test_execute_job_delete_failure_marks_job_failed(
    mock_get_openai_client, db: Session
):
    """
    When CollectionCrud.delete raises (e.g., SQLAlchemyError),
    the job should be marked failed and error_message set.
    """
    project = get_project(db)

    collection = create_collection(db, project)

    job = create_collection_job(db, project, collection)

    mock_get_openai_client.return_value = MagicMock()

    with patch(
        "app.services.collections.delete_collection.Session"
    ) as SessionCtor, patch(
        "app.services.collections.delete_collection.OpenAIAssistantCrud"
    ) as MockAssistantCrud, patch(
        "app.services.collections.delete_collection.CollectionCrud"
    ) as MockCollectionCrud:
        SessionCtor.return_value.__enter__.return_value = db
        SessionCtor.return_value.__exit__.return_value = False

        collection_crud_instance = MockCollectionCrud.return_value
        collection_crud_instance.read_one.return_value = collection
        collection_crud_instance.delete.side_effect = SQLAlchemyError("boom")

        task_id = uuid4()
        req = DeletionRequest(collection_id=collection.id)
        payload = ResponsePayload(status="processing", route="/test/delete")

        execute_job(
            request=req.model_dump(),
            payload_data=asdict(payload),
            project_id=project.id,
            organization_id=project.organization_id,
            task_id=task_id,
            job_id=job.id,
            collection_id=collection.id,
            task_instance=None,
        )

        failed_job = CollectionJobCrud(db, project.id).read_one(job.id)
        assert failed_job.task_id == task_id
        assert failed_job.status == CollectionJobStatus.failed
        assert failed_job.error_message and "boom" in failed_job.error_message

        MockAssistantCrud.assert_called_once()
        MockCollectionCrud.assert_called_with(db, project.id)
