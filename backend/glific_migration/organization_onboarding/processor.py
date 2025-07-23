import csv
import json
import logging

from .client import OnboardingClient
from .validator import CSVValidator

logger = logging.getLogger(__name__)


class OnboardingProcessor:
    def __init__(self, input_filename, output_filename, api_url, api_key):
        self.input_filename = input_filename
        self.output_filename = output_filename
        self.client = OnboardingClient(api_url, api_key)
        self.csv_validator = CSVValidator(['organization_name', 'project_name', 'email', 'password', 'user_name'])
        self.output_headers = [
            'organization_name', 'organization_id',
            'project_name', 'project_id',
            'user_name', 'user_id',
            'api_key',
            'success', 'response_from_endpoint'
        ]

    def create_error_row(self, row, error_message):
        return {
            'organization_name': row.get('organization_name', ''),
            'organization_id': '',
            'project_name': row.get('project_name', ''),
            'project_id': '',
            'user_name': row.get('user_name', ''),
            'user_id': '',
            'api_key': '',
            'success': 'no',
            'response_from_endpoint': error_message
        }

    def run(self):
        try:
            with open(self.input_filename, 'r', newline='', encoding='utf-8') as infile:
                reader = list(csv.DictReader(infile))

                if not reader:
                    logger.error("CSV file is empty.")
                    return

                is_valid, errors = self.csv_validator.validate_rows(reader)
                if not is_valid:
                    logger.error("CSV validation failed:")
                    for e in errors:
                        logger.error(f"  - {e}")
                    print("Validation failed. Check onboarding.log for details.")
                    return

                with open(self.output_filename, 'w', newline='', encoding='utf-8') as outfile:
                    writer = csv.DictWriter(outfile, fieldnames=self.output_headers)
                    writer.writeheader()

                    for row in reader:
                        logger.info(f"Processing: Org='{row.get('organization_name')}', Project='{row.get('project_name')}'")
                        success, response_data = self.client.send(row)

                        if success:
                            logger.info(f"Success: Org='{row['organization_name']}', Project='{row['project_name']}'")
                        else:
                            logger.warning(f"Failed: Org='{row['organization_name']}' - {response_data.get('error')}")

                        writer.writerow({
                            'organization_name': row['organization_name'],
                            'organization_id': response_data.get('organization_id', ''),
                            'project_name': row['project_name'],
                            'project_id': response_data.get('project_id', ''),
                            'user_name': row['user_name'],
                            'user_id': response_data.get('user_id', ''),
                            'api_key': response_data.get('api_key', ''),
                            'success': 'yes' if success else 'no',
                            'response_from_endpoint': json.dumps(response_data)
                        })

        except FileNotFoundError:
            logger.error(f"Input file '{self.input_filename}' not found.")
        except PermissionError:
            logger.error(f"Permission denied to access file '{self.input_filename}'.")
        except csv.Error as e:
            logger.error(f"CSV parsing error: {str(e)}")
        except Exception as e:
            logger.exception(f"Unhandled error in processor: {str(e)}")

        logger.info(f"Onboarding completed. See {self.output_filename} for results.")
