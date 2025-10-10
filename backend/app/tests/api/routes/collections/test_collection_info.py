from uuid import uuid4, UUID
from typing import Optional

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.util import now
from app.models import (
    Collection,
    CollectionJobCreate,
    CollectionActionType,
    CollectionJobStatus,
    CollectionJobUpdate,
)
from app.crud import CollectionJobCrud, CollectionCrud


def create_collection(
    db: Session,
    user,
    with_llm: bool = False,
):
    """Create a Collection row (optionally prefilled with LLM service fields)."""
    llm_service_id = None
    llm_service_name = None
    if with_llm:
        llm_service_id = f"asst_{uuid4()}"
        llm_service_name = "gpt-4o"

    collection = Collection(
        id=uuid4(),
        organization_id=user.organization_id,
        project_id=user.project_id,
        llm_service_id=llm_service_id,
        llm_service_name=llm_service_name,
    )

    return CollectionCrud(db, user.project_id).create(collection)


def create_collection_job(
    db: Session,
    user,
    collection_id: Optional[UUID] = None,
    action_type: CollectionActionType = CollectionActionType.CREATE,
    status: CollectionJobStatus = CollectionJobStatus.PENDING,
):
    """Create a CollectionJob row (uses create schema for clarity)."""
    job_in = CollectionJobCreate(
        collection_id=collection_id,
        project_id=user.project_id,
        action_type=action_type,
        status=status,
    )
    collection_job = CollectionJobCrud(db, user.project_id).create(job_in)

    if collection_job.status == CollectionJobStatus.FAILED:
        job_in = CollectionJobUpdate(
            error_message="Something went wrong during the collection job process."
        )
        collection_job = CollectionJobCrud(db, user.project_id).update(
            collection_job.id, job_in
        )

    return collection_job


def test_collection_info_processing(
    db: Session, client: "TestClient", user_api_key_header, user_api_key
):
    headers = user_api_key_header

    collection_job = create_collection_job(db, user_api_key)

    response = client.get(
        f"{settings.API_V1_STR}/collections/info/jobs/{collection_job.id}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["status"] == CollectionJobStatus.PENDING
    assert data["inserted_at"] is not None
    assert data["collection_id"] == collection_job.collection_id
    assert data["updated_at"] is not None


def test_collection_info_successful(
    db: Session, client: "TestClient", user_api_key_header, user_api_key
):
    headers = user_api_key_header

    collection = create_collection(db, user_api_key, with_llm=True)
    collection_job = create_collection_job(
        db, user_api_key, collection.id, status=CollectionJobStatus.SUCCESSFUL
    )

    response = client.get(
        f"{settings.API_V1_STR}/collections/info/jobs/{collection_job.id}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["id"] == str(collection_job.id)
    assert data["status"] == CollectionJobStatus.SUCCESSFUL
    assert data["action_type"] == CollectionActionType.CREATE
    assert data["collection_id"] == str(collection.id)

    assert data["collection"] is not None
    col = data["collection"]
    assert col["id"] == str(collection.id)
    assert col["llm_service_id"] == collection.llm_service_id
    assert col["llm_service_name"] == "gpt-4o"


def test_collection_info_failed(
    db: Session, client: "TestClient", user_api_key_header, user_api_key
):
    headers = user_api_key_header

    collection_job = create_collection_job(
        db, user_api_key, status=CollectionJobStatus.FAILED
    )

    response = client.get(
        f"{settings.API_V1_STR}/collections/info/jobs/{collection_job.id}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["status"] == CollectionJobStatus.FAILED
    assert data["error_message"] is not None
