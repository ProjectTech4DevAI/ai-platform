import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Tuple, Dict, Optional

logger = logging.getLogger(__name__)


class APIClient:
    """Client for making API requests with retry and error handling."""

    def __init__(self, api_key: str):
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        }
        self.session = requests.Session()
        retries = Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def post(self, url: str, data: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """Make a POST request to the specified URL."""
        try:
            response = self.session.post(
                url, headers=self.headers, json=data, timeout=10
            )
            response.raise_for_status()
            return True, response.json()
        except requests.exceptions.HTTPError as http_err:
            try:
                error_detail = response.json().get("error", "No error detail provided.")
            except Exception:
                error_detail = "Unable to parse error response."
            logger.error(
                "HTTP error while posting to %s: %s | Response error: %s",
                url,
                str(http_err),
                error_detail,
                exc_info=True,
            )
            return False, {"error": error_detail}
        except requests.exceptions.RequestException as e:
            logger.error("Request to %s failed: %s", url, str(e), exc_info=True)
            return False, {"error": str(e)}
