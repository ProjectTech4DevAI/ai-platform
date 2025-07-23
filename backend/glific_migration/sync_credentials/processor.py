import logging
from typing import List, Dict, Set
from glific_migration.base_processor import BaseCSVProcessor
from glific_migration.client import APIClient
from glific_migration.validator import validate_required_fields, is_valid_api_key

logger = logging.getLogger(__name__)


class CredentialProcessor(BaseCSVProcessor):
    """Processor for handling credential migration."""

    HEADERS = ["organization_id", "project_id", "success", "response_from_endpoint"]
    REQUIRED_FIELDS = {"organization_id", "project_id"}

    def __init__(
        self,
        input_file: str,
        output_file: str,
        api_url: str,
        api_key: str,
        openai_key: str,
    ):
        super().__init__(input_file, output_file, self.HEADERS)
        self.client = APIClient(api_key)
        self.api_url = api_url
        self.openai_key = openai_key

    def validate_csv(self, rows: List[Dict[str, str]]) -> bool:
        """Validate CSV data for credential processing."""
        validation_errors = []

        for idx, row in enumerate(rows, start=1):
            row_errors = []

            missing = validate_required_fields(row, self.REQUIRED_FIELDS)
            if missing:
                row_errors.append(f"Missing fields: {', '.join(missing)}")

            try:
                int(row.get("organization_id", ""))
                int(row.get("project_id", ""))
            except ValueError:
                row_errors.append(
                    f"organization_id or project_id is not an integer: org_id='{row.get('organization_id')}', proj_id='{row.get('project_id')}'"
                )

            if row_errors:
                validation_errors.extend(f"Row {idx}: {err}" for err in row_errors)

            if row.get("api_key") and not is_valid_api_key(row["api_key"]):
                validation_errors.append(f"Invalid api_key format: {row['api_key']}")

        if validation_errors:
            logger.error("CSV validation failed with the following issues:")
            for error in validation_errors:
                logger.error(" - %s", error)
            return False

        logger.info("CSV validation passed.")
        return True

    def process_rows(self, rows: List[Dict[str, str]]) -> None:
        """Process rows for credential creation and write to CSV after each request."""
        for idx, row in enumerate(rows, start=1):
            org_id = int(row["organization_id"])
            proj_id = int(row["project_id"])

            payload = {
                "organization_id": org_id,
                "project_id": proj_id,
                "is_active": True,
                "credential": {"openai": {"api_key": self.openai_key}},
            }

            logger.info(
                f"Sending credential request for row {idx} (org: {org_id}, project: {proj_id})..."
            )
            success, resp = self.client.post(self.api_url, data=payload)
            logger.info(f"Row {idx} processed. Success: {success}")

            result = {
                "organization_id": org_id,
                "project_id": proj_id,
                "success": "yes" if success else "no",
                "response_from_endpoint": str(resp),
            }
            self.append_to_csv(result)
