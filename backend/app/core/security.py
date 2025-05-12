from datetime import datetime, timedelta, timezone
from typing import Any
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Generate a key for API key encryption
def get_encryption_key() -> bytes:
    """Generate a key for API key encryption using the app's secret key."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=settings.SECRET_KEY.encode(),
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))


# Initialize Fernet with our encryption key
_fernet = None


def get_fernet() -> Fernet:
    """Get a Fernet instance with the encryption key."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key before storage."""
    try:
        return get_fernet().encrypt(api_key.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to encrypt API key: {str(e)}")


def decrypt_api_key(encrypted_api_key: str) -> str:
    """Decrypt an API key when retrieving it."""
    try:
        return get_fernet().decrypt(encrypted_api_key.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt API key: {str(e)}")


def encrypt_credentials(credentials: dict) -> str:
    """Encrypt the entire credentials object before storage."""
    try:
        # Convert dict to JSON string and encrypt
        import json

        credentials_str = json.dumps(credentials)
        return get_fernet().encrypt(credentials_str.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to encrypt credentials: {str(e)}")


def decrypt_credentials(encrypted_credentials: str) -> dict:
    """Decrypt the entire credentials object when retrieving it."""
    try:
        # Decrypt and parse JSON back to dict
        import json

        decrypted_str = get_fernet().decrypt(encrypted_credentials.encode()).decode()
        return json.loads(decrypted_str)
    except Exception as e:
        raise ValueError(f"Failed to decrypt credentials: {str(e)}")
