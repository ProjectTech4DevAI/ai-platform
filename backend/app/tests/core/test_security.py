import pytest
from uuid import uuid4
from sqlmodel import Session
from app.core.security import (
    get_password_hash,
    verify_password,
    encrypt_api_key,
    decrypt_api_key,
    get_encryption_key,
    APIKeyManager,
)
from app.models import APIKey, User, Organization, Project, AuthContext
from app.tests.utils.test_data import create_test_api_key


def test_encrypt_decrypt_api_key():
    """Test that API key encryption and decryption works correctly."""
    # Test data
    test_key = "ApiKey test123456789"

    # Encrypt the key
    encrypted_key = encrypt_api_key(test_key)

    # Verify encryption worked
    assert encrypted_key is not None
    assert encrypted_key != test_key
    assert isinstance(encrypted_key, str)

    # Decrypt the key
    decrypted_key = decrypt_api_key(encrypted_key)

    # Verify decryption worked
    assert decrypted_key is not None
    assert decrypted_key == test_key


def test_api_key_format_validation():
    """Test that API key format is validated correctly."""
    # Test valid API key format
    valid_key = "ApiKey test123456789"
    encrypted_valid = encrypt_api_key(valid_key)
    assert encrypted_valid is not None
    assert decrypt_api_key(encrypted_valid) == valid_key

    # Test invalid API key format (missing prefix)
    invalid_key = "test123456789"
    encrypted_invalid = encrypt_api_key(invalid_key)
    assert encrypted_invalid is not None
    assert decrypt_api_key(encrypted_invalid) == invalid_key


def test_encrypt_api_key_edge_cases():
    """Test edge cases for API key encryption."""
    # Test empty string
    empty_key = ""
    encrypted_empty = encrypt_api_key(empty_key)
    assert encrypted_empty is not None
    assert decrypt_api_key(encrypted_empty) == empty_key

    # Test whitespace only
    whitespace_key = "   "
    encrypted_whitespace = encrypt_api_key(whitespace_key)
    assert encrypted_whitespace is not None
    assert decrypt_api_key(encrypted_whitespace) == whitespace_key

    # Test very long input
    long_key = "ApiKey " + "a" * 1000
    encrypted_long = encrypt_api_key(long_key)
    assert encrypted_long is not None
    assert decrypt_api_key(encrypted_long) == long_key


def test_encrypt_api_key_type_validation():
    """Test type validation for API key encryption."""
    # Test non-string inputs
    invalid_inputs = [123, [], {}, True]
    for invalid_input in invalid_inputs:
        with pytest.raises(ValueError, match="Failed to encrypt API key"):
            encrypt_api_key(invalid_input)


def test_encrypt_api_key_security():
    """Test security properties of API key encryption."""
    # Test that same input produces different encrypted output
    test_key = "ApiKey test123456789"
    encrypted1 = encrypt_api_key(test_key)
    encrypted2 = encrypt_api_key(test_key)
    assert encrypted1 != encrypted2  # Different encrypted outputs for same input


def test_encrypt_api_key_error_handling():
    """Test error handling in encrypt_api_key."""
    # Test with invalid input
    with pytest.raises(ValueError, match="Failed to encrypt API key"):
        encrypt_api_key(None)


def test_decrypt_api_key_error_handling():
    """Test error handling in decrypt_api_key."""
    # Test with invalid input
    with pytest.raises(ValueError, match="Failed to decrypt API key"):
        decrypt_api_key(None)

    # Test with various invalid encrypted data formats
    invalid_encrypted_data = [
        "invalid_encrypted_data",  # Not base64
        "not_a_base64_string",  # Not base64
        "a" * 44,  # Wrong length
        "!" * 44,  # Invalid base64 chars
        "aGVsbG8=",  # Valid base64 but not encrypted
    ]
    for invalid_data in invalid_encrypted_data:
        with pytest.raises(ValueError, match="Failed to decrypt API key"):
            decrypt_api_key(invalid_data)


def test_get_encryption_key():
    """Test that encryption key generation works correctly."""
    # Get the encryption key
    key = get_encryption_key()

    # Verify the key
    assert key is not None
    assert isinstance(key, bytes)
    # The key is base64 encoded, so it should be 44 bytes
    assert len(key) == 44  # Base64 encoded Fernet key length is 44 bytes


class TestAPIKeyManager:
    """Test suite for APIKeyManager class."""

    def test_generate_returns_correct_tuple(self):
        """Test that generate returns a tuple of (raw_key, key_prefix, key_hash)."""
        raw_key, key_prefix, key_hash = APIKeyManager.generate()

        assert isinstance(raw_key, str)
        assert isinstance(key_prefix, str)
        assert isinstance(key_hash, str)

    def test_generate_raw_key_format(self):
        """Test that generated raw key has correct format."""
        raw_key, key_prefix, key_hash = APIKeyManager.generate()

        # Should start with "ApiKey "
        assert raw_key.startswith(APIKeyManager.PREFIX_NAME)

        # Should have correct length (7 for "ApiKey " + 22 for prefix + 43 for secret)
        expected_length = len(APIKeyManager.PREFIX_NAME) + APIKeyManager.KEY_LENGTH
        assert len(raw_key) == expected_length

    def test_generate_key_prefix_length(self):
        """Test that generated key prefix has correct length."""
        raw_key, key_prefix, key_hash = APIKeyManager.generate()

        assert len(key_prefix) == APIKeyManager.PREFIX_LENGTH

    def test_generate_unique_keys(self):
        """Test that generate creates unique keys on each call."""
        raw_key1, prefix1, hash1 = APIKeyManager.generate()
        raw_key2, prefix2, hash2 = APIKeyManager.generate()

        assert raw_key1 != raw_key2
        assert prefix1 != prefix2
        assert hash1 != hash2

    def test_generate_hash_is_bcrypt(self):
        """Test that the generated hash uses bcrypt format."""
        raw_key, key_prefix, key_hash = APIKeyManager.generate()

        # bcrypt hashes start with $2b$ (or $2a$ or $2y$)
        assert key_hash.startswith("$2")

    def test_extract_key_parts_new_format(self):
        """Test extracting key parts from new format (65 chars)."""
        raw_key, expected_prefix, _ = APIKeyManager.generate()

        result = APIKeyManager._extract_key_parts(raw_key)

        assert result is not None
        extracted_prefix, secret = result
        assert extracted_prefix == expected_prefix
        assert len(secret) == APIKeyManager.KEY_LENGTH - APIKeyManager.PREFIX_LENGTH

    def test_extract_key_parts_old_format(self):
        """Test extracting key parts from old format (43 chars)."""
        old_prefix = "a" * 12
        old_secret = "b" * 31
        raw_key = f"{APIKeyManager.PREFIX_NAME}{old_prefix}{old_secret}"

        result = APIKeyManager._extract_key_parts(raw_key)

        assert result is not None
        extracted_prefix, secret = result
        assert extracted_prefix == old_prefix
        assert secret == old_secret

    def test_extract_key_parts_invalid_prefix(self):
        """Test that invalid prefix returns None."""
        invalid_key = "InvalidPrefix abcdefghij1234567890"

        result = APIKeyManager._extract_key_parts(invalid_key)

        assert result is None

    def test_extract_key_parts_invalid_length(self):
        """Test that invalid length returns None."""
        invalid_key = f"{APIKeyManager.PREFIX_NAME}tooshort"

        result = APIKeyManager._extract_key_parts(invalid_key)

        assert result is None

    def test_verify_valid_key(self, db: Session):
        """Test verifying a valid API key."""
        api_key = create_test_api_key(db)

        auth_context = APIKeyManager.verify(db, api_key.key)

        user = db.get(User, api_key.user_id)
        organization = db.get(Organization, api_key.organization_id)
        project = db.get(Project, api_key.project_id)

        assert auth_context is not None
        assert isinstance(auth_context, AuthContext)
        assert auth_context.user.id == api_key.user_id
        assert auth_context.organization.id == api_key.organization_id
        assert auth_context.project.id == api_key.project_id
        assert auth_context.user == user
        assert auth_context.organization == organization
        assert auth_context.project == project

    def test_verify_invalid_key(self, db: Session):
        """Test verifying an invalid API key."""
        # Generate a key but don't store it
        raw_key, _, _ = APIKeyManager.generate()

        auth_context = APIKeyManager.verify(db, raw_key)

        assert auth_context is None

    def test_verify_wrong_secret(self, db: Session):
        """Test verifying with correct prefix but wrong secret."""
        create_test_api_key(db)

        # Generate a different key to try verification
        raw_key2, _, _ = APIKeyManager.generate()

        # Try to verify with key2 (wrong secret)
        auth_context = APIKeyManager.verify(db, raw_key2)

        assert auth_context is None

    def test_verify_deleted_key(self, db: Session):
        """Test that deleted API keys cannot be verified."""
        api_key_response = create_test_api_key(db)
        raw_key = api_key_response.key

        api_key = db.get(APIKey, api_key_response.id)
        api_key.is_deleted = True
        db.commit()

        auth_context = APIKeyManager.verify(db, raw_key)

        assert auth_context is None

    def test_verify_malformed_key(self, db: Session):
        """Test verifying with malformed key format."""
        malformed_keys = [
            "not_an_api_key",
            "",
            "ApiKey",
            "ApiKey ",
            None,
        ]

        for malformed_key in malformed_keys:
            if malformed_key is not None:
                auth_context = APIKeyManager.verify(db, malformed_key)
                assert auth_context is None

    def test_prefix_name_constant(self):
        """Test that PREFIX_NAME is correct."""
        assert APIKeyManager.PREFIX_NAME == "ApiKey "

    def test_key_length_constants(self):
        """Test that key length constants are correct."""
        assert APIKeyManager.PREFIX_LENGTH == 22
        assert APIKeyManager.KEY_LENGTH == 65
        assert APIKeyManager.KEY_LENGTH == APIKeyManager.PREFIX_LENGTH + 43

    def test_generate_creates_verifiable_key(self, db: Session):
        """Integration test: generated key can be verified."""
        api_key_response = create_test_api_key(db)

        auth_context = APIKeyManager.verify(db, api_key_response.key)

        assert auth_context is not None
        assert auth_context.user.id == api_key_response.user_id
