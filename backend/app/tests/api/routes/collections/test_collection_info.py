import pytest
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.core.config import settings
from app.models import Collection
from app.crud.collection import CollectionCrud
from app.main import app
from app.tests.utils.utils import get_user_from_api_key

client = TestClient(app)


def create_collection(
    db,
    user,
    status: str = "processing",
    with_llm: bool = False,
):
    now = datetime.now(timezone.utc)
    collection = Collection(
        id=uuid4(),
        owner_id=user.user_id,
        organization_id=user.organization_id,
        project_id=user.project_id,
        status=status,
        updated_at=now,
    )
    if with_llm:
        collection.llm_service_id = f"asst_str(uuid4())"
        collection.llm_service_name = "gpt-4o"

    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


def test_collection_info_processing(
    db: Session,
    api_key_headers: dict[str, str],
):
    user = get_user_from_api_key(db, api_key_headers)
    collection = create_collection(db, user, status="processing")

    response = client.post(
        f"{settings.API_V1_STR}/collections/info/{collection.id}",
        headers=api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["id"] == str(collection.id)
    assert data["status"] == "processing"
    assert data["llm_service_id"] is None
    assert data["llm_service_name"] is None


def test_collection_info_successful(
    db: Session,
    api_key_headers: dict[str, str],
):
    user = get_user_from_api_key(db, api_key_headers)
    collection = create_collection(db, user, status="Successful", with_llm=True)

    response = client.post(
        f"{settings.API_V1_STR}/collections/info/{collection.id}",
        headers=api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["id"] == str(collection.id)
    assert data["status"] == "Successful"
    assert data["llm_service_id"] == collection.llm_service_id
    assert data["llm_service_name"] == "gpt-4o"


def test_collection_info_failed(
    db: Session,
    api_key_headers: dict[str, str],
):
    user = get_user_from_api_key(db, api_key_headers)
    collection = create_collection(db, user, status="Failed")

    response = client.post(
        f"{settings.API_V1_STR}/collections/info/{collection.id}",
        headers=api_key_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["id"] == str(collection.id)
    assert data["status"] == "Failed"
    assert data["llm_service_id"] is None
    assert data["llm_service_name"] is None
