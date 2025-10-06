from uuid import uuid4, UUID
from typing import Optional

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.util import now
from app.models import (
    Collection,
    CollectionJob,
    CollectionActionType,
    CollectionJobStatus,
)
from app.crud import CollectionJobCrud, CollectionCrud


def create_collection(
    db,
    user,
    with_llm: bool = False,
):
    collection = Collection(
        id=uuid4(),
        organization_id=user.organization_id,
        project_id=user.project_id,
        inserted_at=now(),
        updated_at=now(),
    )
    if with_llm:
        collection.llm_service_id = f"asst_{uuid4()}"
        collection.llm_service_name = "gpt-4o"

    collection_crud = CollectionCrud(db, user.project_id)
    collection = collection_crud.create(collection)

    return collection


def create_collection_job(
    db,
    user,
    collection_id: Optional[UUID] = None,
    action_type=CollectionActionType.CREATE,
    status=CollectionJobStatus.PENDING,
):
    collection_job = CollectionJob(
        id=uuid4(),
        collection_id=collection_id,
        project_id=user.project_id,
        action_type=action_type,
        status=status,
        inserted_at=now(),
        updated_at=now(),
    )

    if status == CollectionJobStatus.FAILED:
        collection_job.error_message = (
            "Something went wrong during the collection job process."
        )

    collection_job_crud = CollectionJobCrud(db, user.project_id)
    created_job = collection_job_crud.create(collection_job)

    return created_job


def test_collection_info_processing(
    db: Session, client: TestClient, user_api_key_header, user_api_key
):
    headers = user_api_key_header

    collection_job = create_collection_job(db, user_api_key)

    response = client.get(
        f"{settings.API_V1_STR}/collections/info/collection_job/{collection_job.id}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["status"] == CollectionJobStatus.PENDING
    assert data["inserted_at"] is not None
    assert data["collection_id"] == collection_job.collection_id
    assert data["updated_at"] is not None


def test_collection_info_successful(
    db: Session, client: TestClient, user_api_key_header, user_api_key
):
    headers = user_api_key_header

    collection = create_collection(db, user_api_key, with_llm=True)
    collection_job = create_collection_job(
        db, user_api_key, collection.id, status=CollectionJobStatus.SUCCESSFUL
    )

    response = client.get(
        f"{settings.API_V1_STR}/collections/info/collection_job/{collection_job.id}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["id"] == str(collection.id)
    assert data["llm_service_id"] == collection.llm_service_id
    assert data["llm_service_name"] == "gpt-4o"


def test_collection_info_failed(
    db: Session, client: TestClient, user_api_key_header, user_api_key
):
    headers = user_api_key_header

    collection_job = create_collection_job(
        db, user_api_key, status=CollectionJobStatus.FAILED
    )

    response = client.get(
        f"{settings.API_V1_STR}/collections/info/collection_job/{collection_job.id}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["status"] == CollectionJobStatus.FAILED
    assert data["error_message"] is not None
