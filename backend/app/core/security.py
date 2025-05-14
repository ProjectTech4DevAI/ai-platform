"""
Security module for handling authentication, encryption, and password management.
This module provides utilities for:
- JWT token generation and validation
- Password hashing and verification
- API key encryption/decryption
- Credentials encryption/decryption
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import base64
import json

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
ALGORITHM = "HS256"

# Fernet instance for encryption/decryption
_fernet = None


def get_encryption_key() -> bytes:
    """
    Generate a key for API key encryption using the app's secret key.

    Returns:
        bytes: A URL-safe base64 encoded encryption key derived from the app's secret key.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=settings.SECRET_KEY.encode(),
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))


def get_fernet() -> Fernet:
    """
    Get a Fernet instance with the encryption key.
    Uses singleton pattern to avoid creating multiple instances.

    Returns:
        Fernet: A Fernet instance initialized with the encryption key.
    """
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject of the token (typically user ID)
        expires_delta: Token expiration time delta

    Returns:
        str: Encoded JWT token
    """
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to check against

    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Generate a password hash.

    Args:
        password: The plain text password to hash

    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key before storage.

    Args:
        api_key: The plain text API key to encrypt

    Returns:
        str: The encrypted API key

    Raises:
        ValueError: If encryption fails
    """
    try:
        return get_fernet().encrypt(api_key.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to encrypt API key: {str(e)}")


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt an API key when retrieving it.

    Args:
        encrypted_api_key: The encrypted API key to decrypt

    Returns:
        str: The decrypted API key

    Raises:
        ValueError: If decryption fails
    """
    try:
        return get_fernet().decrypt(encrypted_api_key.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt API key: {str(e)}")


def encrypt_credentials(credentials: dict) -> str:
    """
    Encrypt the entire credentials object before storage.

    Args:
        credentials: Dictionary containing credentials to encrypt

    Returns:
        str: The encrypted credentials

    Raises:
        ValueError: If encryption fails
    """
    try:
        credentials_str = json.dumps(credentials)
        return get_fernet().encrypt(credentials_str.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to encrypt credentials: {str(e)}")


def decrypt_credentials(encrypted_credentials: str) -> dict:
    """
    Decrypt the entire credentials object when retrieving it.

    Args:
        encrypted_credentials: The encrypted credentials string to decrypt

    Returns:
        dict: The decrypted credentials dictionary

    Raises:
        ValueError: If decryption fails
    """
    try:
        decrypted_str = get_fernet().decrypt(encrypted_credentials.encode()).decode()
        return json.loads(decrypted_str)
    except Exception as e:
        raise ValueError(f"Failed to decrypt credentials: {str(e)}")
