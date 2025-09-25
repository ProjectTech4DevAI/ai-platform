import pytest
import os
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch
from uuid import UUID
from dataclasses import asdict

from sqlmodel import Session
from moto import mock_aws

from app.core.config import settings
from app.models.collection import (
    CreationRequest,
    Collection,
    ResponsePayload,
    CollectionStatus,
)
from app.crud import CollectionCrud, DocumentCollectionCrud
from app.tests.utils.utils import get_project
from app.tests.utils.collection import get_collection
from app.tests.utils.document import DocumentStore
from app.tests.utils.openai import get_mock_openai_client_with_vector_store
from app.services.collections.create_collection import start_job, execute_job
from app.core.cloud import AmazonCloudStorageClient


@pytest.fixture(scope="function")
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = settings.AWS_DEFAULT_REGION


def test_start_job(db: Session):
    request = CreationRequest(
        model="gpt-4o",
        instructions="string",
        temperature=0.000001,
        documents=[UUID("f3e86a17-1e6f-41ec-b020-5b08eebef928")],
        batch_size=1,
        callback_url=None,
    )
    project = get_project(db)
    collection = Collection(
        id=UUID("42be84e8-d1b0-4e93-8b26-ebb74034674b"),
        project_id=project.id,
        organization_id=project.organization_id,
        status="PENDING",
    )

    with patch(
        "app.services.collections.create_collection.start_low_priority_job"
    ) as mock_schedule:
        mock_schedule.return_value = "fake-task-id"

        job_id = start_job(
            db,
            request.model_dump(),
            collection,
            project.id,
            {"some": "data"},  # payload
            project.organization_id,
        )

        assert job_id == collection.id

        mock_schedule.assert_called_once()
        _, kwargs = mock_schedule.call_args
        assert (
            kwargs["function_path"]
            == "app.services.collections.create_collection.execute_job"
        )
        assert kwargs["project_id"] == project.id
        assert kwargs["organization_id"] == project.organization_id
        assert kwargs["job_id"] == collection.id
        assert kwargs["request"] == request.model_dump()
        assert kwargs["payload_data"] == {"some": "data"}


@pytest.mark.usefixtures("aws_credentials")
@mock_aws
@patch("app.services.collections.create_collection.get_openai_client")
def test_execute_job_success(mock_get_openai_client, db: Session):
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

    collection_obj = get_collection(db, client=mock_client, project_id=project.id)

    crud = CollectionCrud(db, project_id=project.id)
    collection = crud.create(collection_obj)

    job_id = collection.id
    task_id = "task-123"

    with patch("app.services.collections.create_collection.Session") as SessionCtor:
        SessionCtor.return_value.__enter__.return_value = db
        SessionCtor.return_value.__exit__.return_value = False

        execute_job(
            request=sample_request.model_dump(),
            payload_data=asdict(sample_payload),
            project_id=collection.project_id,
            organization_id=collection.organization_id,
            task_id=task_id,
            job_id=job_id,
            task_instance=None,
        )

    updated = CollectionCrud(db, collection.project_id).read_one(job_id)
    assert updated.task_id == task_id
    assert updated.status == CollectionStatus.successful
    assert updated.llm_service_id == "mock_assistant_id"
    assert updated.llm_service_name == sample_request.model
    assert updated.updated_at is not None

    docs = DocumentCollectionCrud(db).read(updated, skip=0, limit=10)
    assert len(docs) == 1
    assert docs[0].fname == document.fname
