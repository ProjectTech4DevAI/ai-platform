import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
import random
import string

from app.main import app
from app.api.deps import get_db
from app.crud.credentials import set_creds_for_org, get_creds_by_org, remove_creds_for_org
from app.models import Creds, CredsCreate, CredsUpdate, Organization, OrganizationCreate
from app.utils import APIResponse
from app.tests.utils.utils import random_lower_string
from app.core.config import settings

client = TestClient(app)

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@pytest.fixture
def create_organization_and_creds(db: Session, superuser_token_headers: dict[str, str]):
    unique_org_name = "Test Organization " + generate_random_string(5)  # Ensure unique name
    org_data = OrganizationCreate(name=unique_org_name, is_active=True)
    org = Organization(**org_data.dict())  # Create Organization instance
    db.add(org)
    db.commit()
    db.refresh(org)  

    creds_data = CredsCreate(
        organization_id=org.id,  
        is_active=True,
        credential={"openai": {"api_key": "sk-" + generate_random_string(10)}}
    )
    return org, creds_data  

def test_set_creds_for_org(db: Session, superuser_token_headers: dict[str, str]):
    unique_org_id = 2  
    existing_org = db.query(Organization).filter(Organization.id == unique_org_id).first()

    if not existing_org:
        new_org = Organization(id=unique_org_id, name="Test Organization", is_active=True)
        db.add(new_org)
        db.commit()

    api_key = "sk-" + generate_random_string(10)
    creds_data = {
        "organization_id": unique_org_id,
        "is_active": True,
        "credential": {
            "openai": {"api_key": api_key}
        }
    }

    response = client.post(
        f"{settings.API_V1_STR}/credentials/", json=creds_data, headers=superuser_token_headers
    )

    assert response.status_code == 200  

    created_creds = response.json()
    assert "data" in created_creds
    assert created_creds["data"]["organization_id"] == unique_org_id
    assert created_creds["data"]["credential"]["openai"]["api_key"] == api_key

# Test reading credentials
def test_read_credentials_with_creds(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    # Create the organization and credentials (this time with credentials)
    org, creds_data = create_organization_and_creds
    # Create credentials for the organization
    set_creds_for_org(session=db, creds_add=creds_data)
    
    # Case 3: Organization exists and credentials are found
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "data" in response_data
    assert response_data["data"]["organization_id"] == org.id
    assert "credential" in response_data["data"]
    assert response_data["data"]["credential"]["openai"]["api_key"] == creds_data.credential["openai"]["api_key"]

def test_read_credentials_not_found(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    # Create the organization without credentials
    org, _ = create_organization_and_creds
    
    # Case 1: Organization exists but no credentials
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}", headers=superuser_token_headers
    )
    
    # Assert that the status code is 404
    assert response.status_code == 404
    response_data = response.json()
    
    # Assert the correct error message
    assert response_data["detail"] == "Credentials not found"

    # Case 2: Organization does not exist
    non_existing_org_id = 999  # Assuming this ID does not exist
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{non_existing_org_id}", headers=superuser_token_headers
    )

    # Assert that the status code is 404
    assert response.status_code == 404
    response_data = response.json()
    
    # Assert the correct error message
    assert response_data["detail"] == "Credentials not found"

def test_read_api_key(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)

    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/api-key", headers=superuser_token_headers
    )
    
    assert response.status_code == 200
    response_data = response.json()
    
    assert "data" in response_data
    
    assert "api_key" in response_data["data"]
    assert response_data["data"]["api_key"] == creds_data.credential["openai"]["api_key"]


def test_read_api_key_not_found(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, _ = create_organization_and_creds
    
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}/api-key", headers=superuser_token_headers
    )
    
    assert response.status_code == 404
    
    response_data = response.json()
    assert response_data["detail"] == "API key not found"

# Test updating credentials
def test_update_credentials(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)
    update_data = {
        "credential": {
            "openai": {"api_key": "sk-" + generate_random_string()}  # Generate a new API key for the update
        }
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/{org.id}", 
        json=update_data, 
        headers=superuser_token_headers
    )

    assert response.status_code == 200
    updated_creds = response.json()["data"]
    assert "credential" in updated_creds
    assert "openai" in updated_creds["credential"]
    assert updated_creds["credential"]["openai"]["api_key"] != creds_data.credential["openai"]["api_key"]

def test_update_credentials_not_found(db: Session, superuser_token_headers: dict[str, str]):
    
    update_data = {
        "credential": {
            "openai": "sk-" + generate_random_string()
        }
    }

    response = client.patch(
        f"{settings.API_V1_STR}/credentials/999", json=update_data, headers=superuser_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Credentials not found"

def test_delete_credentials(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, creds_data = create_organization_and_creds
    set_creds_for_org(session=db, creds_add=creds_data)
    
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/api-key", 
        headers=superuser_token_headers
    )
    
    assert response.status_code == 200
    response_data = response.json()
    print(f"Response Data: {response_data}")
    
    assert "data" in response_data  
    assert "message" in response_data["data"] 
    assert response_data["data"]["message"] == "Credentials deleted successfully"

    
    response = client.get(
        f"{settings.API_V1_STR}/credentials/{org.id}", 
        headers=superuser_token_headers
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Credentials not found"


def test_delete_credentials_not_found(db: Session, superuser_token_headers: dict[str, str], create_organization_and_creds):
    org, _ = create_organization_and_creds
    
    response = client.delete(
        f"{settings.API_V1_STR}/credentials/{org.id}/api-key", 
        headers=superuser_token_headers
    )
    
    assert response.status_code == 404
    response_data = response.json()
    
    assert response_data["detail"] == "Credentials not found"
