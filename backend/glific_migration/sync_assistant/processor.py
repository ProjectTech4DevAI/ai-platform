import logging
from typing import List, Dict, Set
from glific_migration.base_processor import BaseCSVProcessor
from glific_migration.client import APIClient
from glific_migration.validator import (
    validate_required_fields,
    is_valid_api_key,
    is_valid_assistant_id,
)


logger = logging.getLogger(__name__)


class AssistantIngestProcessor(BaseCSVProcessor):
    """Processor for handling assistant ingestion."""

    HEADERS = ["assistant_id", "api_key", "success", "response_from_endpoint"]
    REQUIRED_FIELDS = {"assistant_id", "api_key"}

    def __init__(self, input_file: str, output_file: str, base_url: str):
        super().__init__(input_file, output_file, self.HEADERS)
        self.base_url = base_url.rstrip("/")

    def validate_csv(self, rows: List[Dict[str, str]]) -> bool:
        """Validate CSV data for assistant ingestion."""
        validation_errors = []

        for idx, row in enumerate(rows, start=1):
            row_errors = []

            missing = validate_required_fields(row, self.REQUIRED_FIELDS)
            if missing:
                row_errors.append(f"Missing fields: {', '.join(missing)}")

            if not row.get("assistant_id", "").strip():
                row_errors.append("Empty assistant_id")

            if not row.get("api_key", "").strip():
                row_errors.append("Empty api_key")

            if row.get("assistant_id") and not is_valid_assistant_id(
                row["assistant_id"]
            ):
                row_errors.append(f"Invalid assistant_id format: {row['assistant_id']}")

            if row.get("api_key") and not is_valid_api_key(row["api_key"]):
                row_errors.append(f"Invalid api_key format: {row['api_key']}")

            if row_errors:
                validation_errors.extend(f"Row {idx}: {err}" for err in row_errors)

        if validation_errors:
            logger.error("CSV validation failed with the following issues:")
            for error in validation_errors:
                logger.error(" - %s", error)
            return False

        logger.info("CSV validation passed.")
        return True

    def process_rows(self, rows: List[Dict[str, str]]) -> None:
        """Process rows for assistant ingestion and write to CSV after each request."""
        for idx, row in enumerate(rows, start=1):
            assistant_id = row["assistant_id"]
            api_key = row["api_key"]

            logger.info(
                f"Ingesting assistant for row {idx} (assistant_id: {assistant_id})"
            )
            url = f"{self.base_url}/assistant/{assistant_id}/ingest"
            client = APIClient(api_key=api_key)
            success, resp = client.post(url)
            logger.info(f"Row {idx} processed. Success: {success}")

            result = {
                "assistant_id": assistant_id,
                "api_key": api_key,
                "success": "yes" if success else "no",
                "response_from_endpoint": str(resp),
            }
            self.append_to_csv(result)
