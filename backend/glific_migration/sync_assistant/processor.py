import logging
import csv
from glific_migration.base_processor import BaseCSVProcessor
from glific_migration.client import APIClient

logger = logging.getLogger(__name__)

class AssistantIngestProcessor(BaseCSVProcessor):
    def __init__(self, input_file, output_file, base_url):
        super().__init__(input_file, output_file)
        self.base_url = base_url
        self.headers = [
            'assistant_id', 'api_key',
            'success', 'response_from_endpoint'
        ]

    def run(self):
        logger.info("Loading assistant ingest CSV input...")
        rows = self.load_csv()

        logger.info("Validating CSV rows...")
        self.validate_csv(rows)

        logger.info("Initializing output file...")
        self.init_output_csv()

        logger.info("Processing rows for assistant ingestion...")
        self.process_rows(rows)

        logger.info("Assistant ingestion processing complete.")

    def validate_csv(self, rows: list[dict]):
        required_fields = {"assistant_id", "api_key"}

        for idx, row in enumerate(rows, start=1):
            missing = required_fields - row.keys()
            if missing:
                logger.error(f"Row {idx} missing required fields: {missing}")
                raise ValueError(f"Row {idx} missing required fields: {missing}")

            if not row['assistant_id'].strip() or not row['api_key'].strip():
                logger.error(f"Row {idx} has empty assistant_id or api_key")
                raise ValueError(f"Row {idx} has empty assistant_id or api_key")

    def init_output_csv(self):
        with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()

    def process_rows(self, rows: list[dict]):
        with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)

            for idx, row in enumerate(rows, start=1):
                assistant_id = row['assistant_id']
                api_key = row['api_key']

                logger.info("Ingesting assistant for row %d (assistant_id: %s)", idx, assistant_id)

                url = f"{self.base_url.rstrip('/')}/assistant/{assistant_id}/ingest"
                client = APIClient(api_key=api_key)

                success, resp = client.post(url)
                logger.info("Row %d processed. Success: %s", idx, success)

                result = {
                    "assistant_id": assistant_id,
                    "api_key": api_key,
                    "success": 'yes' if success else 'no',
                    "response_from_endpoint": str(resp)
                }

                writer.writerow(result)
