from email_validator import validate_email, EmailNotValidError
from typing import List, Dict, Tuple, Set
import re


def validate_required_fields(row: Dict[str, str], fields: Set[str]) -> List[str]:
    """Validate that required fields are present and non-empty."""
    return [f for f in fields if f not in row or not row[f].strip()]


def validate_email_format(email: str) -> Tuple[bool, str]:
    """Validate email format."""
    try:
        validate_email(email, check_deliverability=False)
        return True, ""
    except EmailNotValidError as e:
        return False, str(e)


def validate_password(password: str) -> bool:
    """Validate password length."""
    return len(password) >= 8


def is_valid_api_key(api_key: str) -> bool:
    """
    Validates that the API key is in the format:
    'ApiKey <43-character base64url-like token>'
    """
    pattern = r"^ApiKey [A-Za-z0-9_-]{43}$"
    return bool(re.fullmatch(pattern, api_key))


def is_valid_assistant_id(assistant_id: str) -> bool:
    """
    Validates OpenAI assistant ID. Should start with 'asst_' followed by 15+ alphanumeric chars.
    """
    pattern = r"^asst_[a-zA-Z0-9]{15,}$"
    return bool(re.fullmatch(pattern, assistant_id))
