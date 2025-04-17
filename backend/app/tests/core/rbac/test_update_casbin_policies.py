import os
import json
import pytest
from pathlib import Path
from sqlmodel import Session, select

from app.core.rbac.update_casbin_policies import update_policies, main, policies_file_path
from app.core.db import engine
from app.models import CasbinRule


def test_update_policies_success(db: Session):
    """Test successful policy update and file-based resource check"""

    # Execute the policy update function
    update_policies(db)

    # Fetch all 'p' type policies from the database
    result = db.exec(
        select(CasbinRule).where(CasbinRule.ptype == "p")
    ).all()

    db_policies = {(row.v0, row.v1, row.v2) for row in result}

    # Load and parse the policy file
    assert Path(policies_file_path).exists(), f"Policy file not found: {policies_file_path}"
    with open(policies_file_path, "r") as f:
        data = json.load(f)

    expected_policies = set()
    for perm in data["permissions"]:
        role = perm["role"]
        resource = perm["resource"]
        actions = perm["actions"]
        for action in actions:
            expected_policies.add((role, resource, action))

    # Compare
    missing = expected_policies - db_policies
    extra = db_policies - expected_policies

    assert not missing, f"Missing policies: {missing}"
    assert not extra, f"Unexpected policies in DB: {extra}"


def test_update_policies_invalid_file(db: Session):
    """Test handling of invalid policy file"""
    # Backup original file path
    original_path = policies_file_path
    backup_path = original_path + ".bak"
    
    try:
        # Rename the file to simulate it being missing
        if os.path.exists(original_path):
            os.rename(original_path, backup_path)
        
        with pytest.raises(ValueError, match="Policy file not found"):
            update_policies(db)
    finally:
        # Restore the file
        if os.path.exists(backup_path):
            os.rename(backup_path, original_path)


def test_update_policies_invalid_data(db: Session):
    """Test handling of invalid policy data"""
    # Backup original file
    original_path = policies_file_path
    backup_path = original_path + ".bak"
    
    try:
        # Backup the original file
        if os.path.exists(original_path):
            os.rename(original_path, backup_path)
        
        # Create invalid policy file
        with open(original_path, "w") as f:
            json.dump({"permissions": [{"invalid": "data"}]}, f)
        
        with pytest.raises(ValueError, match="Invalid policy entry"):
            update_policies(db)
    finally:
        # Restore the original file
        if os.path.exists(backup_path):
            if os.path.exists(original_path):
                os.remove(original_path)
            os.rename(backup_path, original_path)


def test_main_success(db: Session):
    """Test main function success case"""
    # This test will use the actual database and file
    main()
    
    policies = db.exec(
        select(CasbinRule).where(CasbinRule.ptype == "p")
    ).all()
    assert len(policies) > 0
