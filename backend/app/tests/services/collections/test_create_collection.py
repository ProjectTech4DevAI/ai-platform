# tests/services/collections/test_create_collection_jobs.py

import os
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from moto import mock_aws
from sqlmodel import Session

from app.core.cloud import AmazonCloudStorageClient
from app.core.config import settings
from app.crud import CollectionCrud, CollectionJobCrud, DocumentCollectionCrud
from app.models import CollectionJobStatus, CollectionJob
from app.models.collection import CreationRequest, ResponsePayload
from app.services.collections.create_collection import start_job, execute_job
from app.tests.utils.openai import get_mock_openai_client_with_vector_store
from app.tests.utils.utils import get_project
from app.tests.utils.document import DocumentStore


@pytest.fixture(scope="function")
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = settings.AWS_DEFAULT_REGION


def test_start_job_creates_collection_job_and_schedules_task(db: Session):
    """
    start_job should:
      - create a CollectionJob in 'processing'
      - call start_low_priority_job with the correct kwargs
      - return the job UUID (same one that was passed in)
    """
    project = get_project(db)
    request = CreationRequest(
        model="gpt-4o",
        instructions="string",
        temperature=0.000001,
        documents=[UUID("f3e86a17-1e6f-41ec-b020-5b08eebef928")],
        batch_size=1,
        callback_url=None,
    )
    payload = {"some": "data"}
    job_id = uuid4()

    with patch(
        "app.services.collections.create_collection.start_low_priority_job"
    ) as mock_schedule:
        mock_schedule.return_value = "fake-task-id"

        returned_job_id = start_job(
            db=db,
            request=request.model_dump(),
            project_id=project.id,
            payload=payload,
            collection_job_id=job_id,
            organization_id=project.organization_id,
        )

        assert returned_job_id == job_id

        job = CollectionJobCrud(db, project.id).read_one(job_id)
        assert job.id == job_id
        assert job.project_id == project.id
        assert job.status == CollectionJobStatus.processing
        assert job.action_type == "create"
        assert job.collection_id is None

        mock_schedule.assert_called_once()
        kwargs = mock_schedule.call_args.kwargs
        assert (
            kwargs["function_path"]
            == "app.services.collections.create_collection.execute_job"
        )
        assert kwargs["project_id"] == project.id
        assert kwargs["organization_id"] == project.organization_id
        assert kwargs["job_id"] == job_id
        assert kwargs["request"] == request.model_dump()
        assert kwargs["payload_data"] == payload


@pytest.mark.usefixtures("aws_credentials")
@mock_aws
@patch("app.services.collections.create_collection.get_openai_client")
def test_execute_job_success_flow_updates_job_and_creates_collection(
    mock_get_openai_client, db: Session
):
    """
    execute_job should:
      - set task_id on the CollectionJob
      - ingest documents into a vector store
      - create an OpenAI assistant
      - create a Collection with llm fields filled
      - link the CollectionJob -> collection_id, set status=successful
      - create DocumentCollection links
    """
    project = get_project(db)

    aws = AmazonCloudStorageClient()
    aws.create()

    store = DocumentStore(db=db, project_id=project.id)
    document = store.put()
    s3_key = Path(urlparse(document.object_store_url).path).relative_to("/")
    aws.client.put_object(Bucket=settings.AWS_S3_BUCKET, Key=str(s3_key), Body=b"test")

    sample_request = CreationRequest(
        model="gpt-4o",
        instructions="string",
        temperature=0.000001,
        documents=[document.id],
        batch_size=1,
        callback_url=None,
    )
    sample_payload = ResponsePayload(status="pending", route="/test/route")

    mock_client = get_mock_openai_client_with_vector_store()
    mock_get_openai_client.return_value = mock_client

    job_id = uuid4()
    job_crud = CollectionJobCrud(db, project.id)
    job_crud.create(
        CollectionJob(
            id=job_id,
            project_id=project.id,
            status=CollectionJobStatus.processing,
            action_type="create",
        )
    )

    task_id = uuid4()

    with patch("app.services.collections.create_collection.Session") as SessionCtor:
        SessionCtor.return_value.__enter__.return_value = db
        SessionCtor.return_value.__exit__.return_value = False

        execute_job(
            request=sample_request.model_dump(),
            payload_data=asdict(sample_payload),
            project_id=project.id,
            organization_id=project.organization_id,
            task_id=task_id,
            job_id=job_id,
            task_instance=None,
        )

    updated_job = CollectionJobCrud(db, project.id).read_one(job_id)
    assert updated_job.task_id == task_id
    assert updated_job.status == CollectionJobStatus.successful
    assert updated_job.collection_id is not None

    created_collection = CollectionCrud(db, project.id).read_one(
        updated_job.collection_id
    )
    assert created_collection.llm_service_id == "mock_assistant_id"
    assert created_collection.llm_service_name == sample_request.model
    assert created_collection.updated_at is not None

    docs = DocumentCollectionCrud(db).read(created_collection, skip=0, limit=10)
    assert len(docs) == 1
    assert docs[0].fname == document.fname
