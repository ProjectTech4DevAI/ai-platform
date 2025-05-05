import pytest
from app.core.security import (
    get_password_hash,
    verify_password,
    encrypt_api_key,
    decrypt_api_key,
    get_encryption_key,
)


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
