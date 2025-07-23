import logging
import csv
from glific_migration.base_processor import BaseCSVProcessor
from glific_migration.client import APIClient

logger = logging.getLogger(__name__)

class CredentialProcessor(BaseCSVProcessor):
    def __init__(self, input_file, output_file, api_url, api_key, openai_key):
        super().__init__(input_file, output_file)
        self.client = APIClient(api_key)
        self.api_url = api_url
        self.openai_key = openai_key
        self.headers = [
            'organization_id', 'project_id',
            'success', 'response_from_endpoint'
        ]

    def run(self):
        logger.info("Loading CSV input...")
        rows = self.load_csv()

        logger.info("Validating input data...")
        self.validate_csv(rows)

        logger.info("Initializing output file if needed...")
        self.init_output_csv()

        logger.info("Processing rows for credential creation...")
        self.process_rows(rows)

        logger.info("Credential processing complete.")

    def validate_csv(self, rows: list[dict]):
        required_fields = {"organization_id", "project_id"}

        for idx, row in enumerate(rows, start=1):
            missing = required_fields - row.keys()
            if missing:
                logger.error(f"Row {idx} is missing required fields: {missing}")
                raise ValueError(f"Row {idx} is missing required fields: {missing}")

            try:
                int(row['organization_id'])
                int(row['project_id'])
            except ValueError:
                logger.error(f"Row {idx} has non-integer organization_id or project_id: {row}")
                raise ValueError(f"Row {idx} has non-integer organization_id or project_id")

    def init_output_csv(self):
        """Initialize CSV file with headers (overwrite if already exists)."""
        with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()

    def process_rows(self, rows: list[dict]):
        with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)

            for idx, row in enumerate(rows, start=1):
                org_id = int(row['organization_id'])
                proj_id = int(row['project_id'])

                payload = {
                    "organization_id": org_id,
                    "project_id": proj_id,
                    "is_active": True,
                    "credential": {
                        "openai": {
                            "api_key": self.openai_key
                        }
                    }
                }

                logger.info("Sending credential request for row %d (org: %s, project: %s)...", idx, org_id, proj_id)
                success, resp = self.client.post(self.api_url, data=payload)
                logger.info("Row %d processed. Success: %s", idx, success)

                result = {
                    "organization_id": org_id,
                    "project_id": proj_id,
                    "success": 'yes' if success else 'no',
                    "response_from_endpoint": str(resp)
                }

                writer.writerow(result)
