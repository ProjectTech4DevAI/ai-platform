import logging
import json
import csv
from glific_migration.base_processor import BaseCSVProcessor
from glific_migration.validator import validate_required_fields, validate_email_format, validate_password
from glific_migration.client import APIClient

logger = logging.getLogger(__name__)

class OnboardProcessor(BaseCSVProcessor):
    def __init__(self, input_file, output_file, api_url, api_key):
        super().__init__(input_file, output_file)
        self.client = APIClient(api_key)
        self.api_url = api_url
        self.headers = [
            'organization_name', 'organization_id',
            'project_name', 'project_id',
            'user_name', 'user_id', 'api_key',
            'success', 'response_from_endpoint'
        ]

    def run(self):
        logger.info("Loading CSV input...")
        rows = self.load_csv()

        logger.info("Validating CSV rows...")
        if not self.validate_csv(rows):
            logger.error("Validation failed. Aborting processing.")
            return

        logger.info("Creating output CSV and writing headers...")
        self.init_output_csv()

        logger.info("Processing rows and writing results...")
        self.process_rows(rows)

        logger.info("Processing complete. Output written to %s", self.output_file)


    def validate_csv(self, rows: list[dict]) -> bool:
        seen_projects = set()
        validation_errors = []

        for i, row in enumerate(rows, start=2):
            row_errors = []

            missing = validate_required_fields(row, ['organization_name', 'project_name', 'email', 'password', 'user_name'])
            if missing:
                row_errors.append(f"Row {i}: Missing fields: {', '.join(missing)}")

            project_name = row.get('project_name', '')
            if project_name in seen_projects:
                row_errors.append(f"Row {i}: Duplicate project name '{project_name}'")
            else:
                seen_projects.add(project_name)

            ok, msg = validate_email_format(row.get('email', ''))
            if not ok:
                row_errors.append(f"Row {i}: Invalid email: {msg}")

            if not validate_password(row.get('password', '')):
                row_errors.append(f"Row {i}: Password must be at least 8 characters")

            if row_errors:
                validation_errors.extend(row_errors)

        if validation_errors:
            logger.error("CSV validation failed with the following issues:")
            for error in validation_errors:
                logger.error(" - %s", error)
            return False

        logger.info("CSV validation passed.")
        return True

    def init_output_csv(self):
        """Initialize CSV file with headers (overwrite if already exists)."""
        with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()

    def process_rows(self, rows: list[dict]):
        with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)

            for idx, row in enumerate(rows, start=1):
                logger.info("Sending API request for row %d (project: %s)...", idx, row.get('project_name', ''))
                success, resp = self.client.post(self.api_url, data=row)
                logger.info("Row %d processed. Success: %s", idx, success)

                row_result = {
                    **row,
                    'success': 'yes' if success else 'no',
                    'response_from_endpoint': str(resp)
                }
                row_result.update(resp if success else {})

                filtered = {k: row_result.get(k, '') for k in self.headers}
                writer.writerow(filtered)
                