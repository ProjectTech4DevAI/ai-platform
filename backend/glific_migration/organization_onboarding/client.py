import json
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class OnboardingClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'X-API-KEY': api_key,
        }
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def send(self, row):
        payload = {
            "organization_name": row['organization_name'],
            "project_name": row['project_name'],
            "email": row['email'],
            "password": row['password'],
            "user_name": row['user_name'],
        }

        try:
            response = self.session.post(self.api_url, headers=self.headers, json=payload, timeout=10)
            response_json = response.json()
            success = (
                response.status_code == 200 and
                all(k in response_json for k in ['organization_id', 'project_id', 'user_id', 'api_key'])
            )
            return success, {k: v for k, v in response_json.items() if k != 'password'}
        except requests.exceptions.Timeout:
            return False, {"error": "Request timed out"}
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}
        except json.JSONDecodeError as e:
            return False, {"error": f"Invalid JSON response: {str(e)}"}
        except Exception as e:
            logger.exception("Unexpected error during API call")
            return False, {"error": f"Unexpected error: {str(e)}"}
