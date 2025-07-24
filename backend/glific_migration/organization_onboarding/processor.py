import logging
from typing import List, Dict, Set
from glific_migration.base_processor import BaseCSVProcessor
from glific_migration.client import APIClient
from glific_migration.validator import (
    validate_required_fields,
    validate_email_format,
    validate_password,
)

logger = logging.getLogger(__name__)


class OnboardProcessor(BaseCSVProcessor):
    """Processor for handling organization onboarding."""

    HEADERS = [
        "organization_name",
        "organization_id",
        "project_name",
        "project_id",
        "user_name",
        "user_id",
        "api_key",
        "success",
        "response_from_endpoint",
    ]
    REQUIRED_FIELDS = {
        "organization_name",
        "project_name",
        "email",
        "password",
        "user_name",
    }

    def __init__(self, input_file: str, output_file: str, api_url: str, api_key: str):
        super().__init__(input_file, output_file, self.HEADERS)
        self.client = APIClient(api_key)
        self.api_url = api_url

    def validate_csv(self, rows: List[Dict[str, str]]) -> bool:
        """Validate CSV data for organization onboarding."""
        seen_projects = set()
        validation_errors = []

        for idx, row in enumerate(rows, start=1):
            row_errors = []

            missing = validate_required_fields(row, self.REQUIRED_FIELDS)
            if missing:
                row_errors.append(f"Missing fields: {', '.join(missing)}")

            project_name = row.get("project_name", "")
            if project_name in seen_projects:
                row_errors.append(f"Duplicate project name '{project_name}'")
            else:
                seen_projects.add(project_name)

            ok, msg = validate_email_format(row.get("email", ""))
            if not ok:
                row_errors.append(f"Invalid email: {msg}")

            if not validate_password(row.get("password", "")):
                row_errors.append("Password must be at least 8 characters")

            if row_errors:
                validation_errors.extend(f"Row {idx}: {error}" for error in row_errors)

        if validation_errors:
            logger.error("CSV validation failed with the following issues:")
            for error in validation_errors:
                logger.error(" - %s", error)
            return False

        logger.info("CSV validation passed.")
        return True

    def process_rows(self, rows: List[Dict[str, str]]) -> None:
        """Process rows for organization onboarding and write to CSV after each request."""
        for idx, row in enumerate(rows, start=1):
            logger.info(
                f"Sending API request for row {idx} (project: {row.get('project_name', '')})..."
            )
            success, resp = self.client.post(self.api_url, data=row)
            logger.info(f"Row {idx} processed. Success: {success}")

            row_result = {
                **row,
                "success": "yes" if success else "no",
                "response_from_endpoint": str(resp),
            }
            row_result.update(resp if success else {})
            self.append_to_csv({k: row_result.get(k, "") for k in self.HEADERS})
