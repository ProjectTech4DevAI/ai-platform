from unittest.mock import patch
import pytest
import os
from uuid import uuid4
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from sqlmodel import Session
from moto import mock_aws

from app.models.collection import (
    DeletionRequest,
    Collection,
    CollectionStatus,
    ResponsePayload,
)
from app.tests.utils.utils import get_project
from app.crud import CollectionCrud
from app.core.config import settings
from app.tests.utils.collection import get_collection
from app.tests.utils.document import DocumentStore
from app.tests.utils.openai import get_mock_openai_client_with_vector_store
from app.services.collections.delete_collection import start_job, execute_job
from app.core.cloud import AmazonCloudStorageClient


@pytest.fixture(scope="function")
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = settings.AWS_DEFAULT_REGION


def test_start_job(db: Session):
    req = DeletionRequest(collection_id=str(uuid4()))
    project = get_project(db)

    collection = Collection(
        id=req.collection_id,
        project_id=project.id,
        organization_id=project.organization_id,
        status=CollectionStatus.processing,
    )

    payload = {"status": "processing"}

    with patch(
        "app.services.collections.delete_collection.start_low_priority_job"
    ) as mock_schedule:
        mock_schedule.return_value = "fake-task-id"

        job_id = start_job(
            db=db,
            request=req.model_dump(),
            collection=collection,
            project_id=project.id,
            payload=payload,
            organization_id=project.organization_id,
        )

    assert job_id == collection.id

    mock_schedule.assert_called_once()
    _, kwargs = mock_schedule.call_args
    assert (
        kwargs["function_path"]
        == "app.services.collections.delete_collection.execute_job"
    )
    assert kwargs["project_id"] == project.id
    assert kwargs["organization_id"] == project.organization_id
    assert kwargs["job_id"] == collection.id
    assert kwargs["request"] == req.model_dump()
    assert kwargs["payload_data"] == payload


@pytest.mark.usefixtures("aws_credentials")
@mock_aws
@patch("app.services.collections.delete_collection.get_openai_client")
def test_execute_job_delete_success(mock_get_openai_client, db: Session):
    project = get_project(db)

    aws = AmazonCloudStorageClient()
    aws.create()

    store = DocumentStore(db=db, project_id=project.id)
    document = store.put()
    s3_key = Path(urlparse(document.object_store_url).path).relative_to("/")
    aws.client.put_object(Bucket=settings.AWS_S3_BUCKET, Key=str(s3_key), Body=b"test")

    mock_client = get_mock_openai_client_with_vector_store()
    mock_get_openai_client.return_value = mock_client

    collection_obj = get_collection(db, client=mock_client, project_id=project.id)
    crud = CollectionCrud(db, project_id=project.id)
    collection = crud.create(collection_obj, [document])
    db.flush()
    db.commit()

    job_id = collection.id
    task_id = "task-123"
    req = DeletionRequest(collection_id=job_id)
    payload = ResponsePayload(status="pending", route="/test/route")

    with patch(
        "app.services.collections.delete_collection.Session"
    ) as SessionCtor, patch(
        "app.services.collections.delete_collection.OpenAIAssistantCrud"
    ) as MockAssistantCrud:
        SessionCtor.return_value.__enter__.return_value = db
        SessionCtor.return_value.__exit__.return_value = False

        MockAssistantCrud.return_value.delete.return_value = None

        execute_job(
            request=req.model_dump(),
            payload_data=asdict(payload),
            project_id=project.id,
            organization_id=project.organization_id,
            task_id=task_id,
            job_id=job_id,
            task_instance=None,
        )

    updated = CollectionCrud(db, project.id).read_one(job_id)
    assert updated.task_id == task_id
    assert updated.deleted_at is not None

    mock_get_openai_client.assert_called_once()
    MockAssistantCrud.return_value.delete.assert_called_once()
