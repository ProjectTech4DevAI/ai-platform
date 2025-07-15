import json
from pathlib import Path
from typing import Dict
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

SEED_DATA_PATH = (
    Path(__file__).resolve().parents[3] / "app" / "seed_data" / "seed_data.json"
)


def load_seed_data() -> Dict[str, list]:
    """
    Load the list of API keys from seed_data.json.
    """
    with open(SEED_DATA_PATH) as f:
        return json.load(f)


def get_api_key_by_user_email(user_email: str) -> str:
    """
    Retrieve the API key for a given user email from the seed data.
    Raises ValueError if the user is not found.
    """
    seed_data = load_seed_data()
    for apikey in seed_data.get("apikeys", []):
        if apikey["user_email"] == user_email:
            return apikey["api_key"]
    raise ValueError(f"API key for {user_email} not found.")
