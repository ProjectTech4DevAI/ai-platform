"""
Migration script to convert encrypted API keys to hashed format.

This script:
1. Decrypts existing API keys from the old encrypted format
2. Extracts the prefix and secret from the decrypted keys
3. Hashes the secret using bcrypt
4. Generates UUID4 for the new primary key
5. Stores the prefix, hash, and UUID in the new format for backward compatibility

The format is: "ApiKey {12-char-prefix}{31-char-secret}" (total 43 chars)
"""

import logging
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
from passlib.context import CryptContext

from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)

# Use the same hash algorithm as APIKeyManager
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Old format constants
OLD_PREFIX_NAME = "ApiKey "
OLD_PREFIX_LENGTH = 12
OLD_SECRET_LENGTH = 31
OLD_KEY_LENGTH = 43  # Total: 12 + 31


def migrate_api_keys(session: Session, generate_uuid: bool = False) -> None:
    """
    Migrate all existing API keys from encrypted format to hashed format.

    This function:
    1. Fetches all API keys with the old 'key' column
    2. Decrypts each key
    3. Extracts prefix and secret
    4. Hashes the secret
    5. Generates UUID4 for new_id column if generate_uuid is True
    6. Updates key_prefix, key_hash, and optionally new_id columns

    Args:
        session: SQLAlchemy database session
        generate_uuid: Whether to generate and set UUID for new_id column
    """
    logger.info("[migrate_api_keys] Starting API key migration from encrypted to hashed format")

    try:
        # Fetch all API keys that have the old 'key' column
        result = session.execute(
            text("SELECT id, key FROM apikey WHERE key IS NOT NULL")
        )
        api_keys = result.fetchall()

        if not api_keys:
            logger.info("[migrate_api_keys] No API keys found to migrate")
            return

        logger.info(f"[migrate_api_keys] Found {len(api_keys)} API keys to migrate")

        migrated_count = 0
        failed_count = 0

        for row in api_keys:
            key_id = row[0]
            encrypted_key = row[1]

            try:
                # Decrypt the API key
                decrypted_key = decrypt_api_key(encrypted_key)

                # Validate format
                if not decrypted_key.startswith(OLD_PREFIX_NAME):
                    logger.error(
                        f"[migrate_api_keys] Invalid key format for ID {key_id}: "
                        f"does not start with '{OLD_PREFIX_NAME}'"
                    )
                    failed_count += 1
                    continue

                # Extract the key part (after "ApiKey ")
                key_part = decrypted_key[len(OLD_PREFIX_NAME):]

                if len(key_part) != OLD_KEY_LENGTH:
                    logger.error(
                        f"[migrate_api_keys] Invalid key length for ID {key_id}: "
                        f"expected {OLD_KEY_LENGTH}, got {len(key_part)}"
                    )
                    failed_count += 1
                    continue

                # Extract prefix and secret
                key_prefix = key_part[:OLD_PREFIX_LENGTH]
                secret_key = key_part[OLD_PREFIX_LENGTH:]

                # Hash the secret
                key_hash = pwd_context.hash(secret_key)

                # Generate UUID if requested
                if generate_uuid:
                    new_uuid = uuid.uuid4()
                    # Update the record with prefix, hash, and UUID
                    session.execute(
                        text(
                            "UPDATE apikey SET key_prefix = :prefix, key_hash = :hash, new_id = :new_id "
                            "WHERE id = :id"
                        ),
                        {"prefix": key_prefix, "hash": key_hash, "new_id": new_uuid, "id": key_id}
                    )
                else:
                    # Update the record with prefix and hash only
                    session.execute(
                        text(
                            "UPDATE apikey SET key_prefix = :prefix, key_hash = :hash "
                            "WHERE id = :id"
                        ),
                        {"prefix": key_prefix, "hash": key_hash, "id": key_id}
                    )

                migrated_count += 1
                logger.info(
                    f"[migrate_api_keys] Successfully migrated key ID {key_id} "
                    f"with prefix {key_prefix[:4]}..."
                )

            except Exception as e:
                logger.error(
                    f"[migrate_api_keys] Failed to migrate key ID {key_id}: {str(e)}",
                    exc_info=True
                )
                failed_count += 1
                continue

        logger.info(
            f"[migrate_api_keys] Migration completed: "
            f"{migrated_count} successful, {failed_count} failed"
        )

    except Exception as e:
        logger.error(
            f"[migrate_api_keys] Fatal error during migration: {str(e)}",
            exc_info=True
        )
        raise


def verify_migration(session: Session) -> bool:
    """
    Verify that all API keys have been migrated successfully.

    Args:
        session: SQLAlchemy database session

    Returns:
        bool: True if all keys are migrated, False otherwise
    """
    try:
        # Check for any keys with NULL key_prefix or key_hash
        result = session.execute(
            text(
                "SELECT COUNT(*) FROM apikey "
                "WHERE key_prefix IS NULL OR key_hash IS NULL"
            )
        )
        null_count = result.scalar()

        if null_count > 0:
            logger.warning(
                f"[verify_migration] Found {null_count} API keys with NULL "
                "key_prefix or key_hash"
            )
            return False

        # Check total count
        result = session.execute(text("SELECT COUNT(*) FROM apikey"))
        total_count = result.scalar()

        logger.info(
            f"[verify_migration] All {total_count} API keys have been "
            "successfully migrated"
        )
        return True

    except Exception as e:
        logger.error(
            f"[verify_migration] Error verifying migration: {str(e)}",
            exc_info=True
        )
        return False
