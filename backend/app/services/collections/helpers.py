import logging
import json
import ast
import re
from dataclasses import asdict, replace

from pydantic import HttpUrl
from openai import OpenAIError

from app.core.util import post_callback
from app.models.collection import ResponsePayload
from app.crud.rag import OpenAIAssistantCrud
from app.utils import APIResponse


logger = logging.getLogger(__name__)


def extract_error_message(err: Exception) -> str:
    err_str = str(err).strip()

    body = re.sub(r"^Error code:\s*\d+\s*-\s*", "", err_str)
    message = None
    try:
        payload = json.loads(body)
        if isinstance(payload, dict):
            message = payload.get("error", {}).get("message")
    except Exception:
        pass

    if message is None:
        try:
            payload = ast.literal_eval(body)
            if isinstance(payload, dict):
                message = payload.get("error", {}).get("message")
        except Exception:
            pass

    if not message:
        message = body

    return message.strip()[:1000]


class CallbackHandler:
    def __init__(self, payload: ResponsePayload):
        self.payload = payload

    def fail(self, body):
        raise NotImplementedError()

    def success(self, body):
        raise NotImplementedError()


class SilentCallback(CallbackHandler):
    def fail(self, body):
        logger.info(f"[SilentCallback.fail] Silent callback failure")
        return

    def success(self, body):
        logger.info(f"[SilentCallback.success] Silent callback success")
        return


class WebHookCallback(CallbackHandler):
    def __init__(self, url: HttpUrl, payload: ResponsePayload):
        super().__init__(payload)
        self.url = url
        logger.info(
            f"[WebHookCallback.init] Initialized webhook callback | {{'url': '{url}'}}"
        )

    def __call__(self, response: APIResponse, status: str):
        time = ResponsePayload.now()
        payload = replace(self.payload, status=status, time=time)
        response.metadata = asdict(payload)
        logger.info(
            f"[WebHookCallback.call] Posting callback | {{'url': '{self.url}', 'status': '{status}'}}"
        )
        post_callback(self.url, response)

    def fail(self, body):
        logger.warning(f"[WebHookCallback.fail] Callback failed | {{'body': '{body}'}}")
        self(APIResponse.failure_response(body), "incomplete")

    def success(self, body):
        logger.info(f"[WebHookCallback.success] Callback succeeded")
        self(APIResponse.success_response(body), "complete")


def _backout(crud: OpenAIAssistantCrud, assistant_id: str):
    try:
        crud.delete(assistant_id)
    except OpenAIError as err:
        logger.error(
            f"[backout] Failed to delete assistant | {{'assistant_id': '{assistant_id}', 'error': '{str(err)}'}}",
            exc_info=True,
        )
