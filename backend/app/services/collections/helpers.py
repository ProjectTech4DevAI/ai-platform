import logging
import json
import ast
import re
from uuid import UUID
from typing import List

from pydantic import HttpUrl
from openai import OpenAIError

from app.core.util import post_callback
from app.crud.document import DocumentCrud
from app.utils import APIResponse


logger = logging.getLogger(__name__)


def extract_error_message(err: Exception) -> str:
    """Extract a concise, user-facing message from an exception, preferring `error.message`
    in JSON/dict bodies after stripping prefixes.Falls back to cleaned text and truncates to
    1000 characters."""
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


def batch_documents(
    document_crud: DocumentCrud, documents: List[UUID], batch_size: int
):
    """Batch document IDs into chunks of size `batch_size`, load each via `DocumentCrud.read_each`,
    and return a list of document batches."""

    logger.info(
        f"[batch_documents] Starting batch iteration for documents | {{'batch_size': {batch_size}, 'total_documents': {len(documents)}}}"
    )
    docs_batches = []
    start, stop = 0, batch_size
    while True:
        view = documents[start:stop]
        if not view:
            break
        batch_docs = document_crud.read_each(view)
        docs_batches.append(batch_docs)
        start = stop
        stop += batch_size
    return docs_batches


class CallbackHandler:
    def __init__(self, collection_job):
        self.collection_job = collection_job

    def fail(self, body):
        raise NotImplementedError()

    def success(self, body):
        raise NotImplementedError()


class SilentCallback(CallbackHandler):
    def fail(self, body):
        logger.info("[SilentCallback.fail] Silent callback failure")
        return

    def success(self, body):
        logger.info("[SilentCallback.success] Silent callback success")
        return


class WebHookCallback(CallbackHandler):
    def __init__(self, url: HttpUrl, collection_job):
        super().__init__(collection_job)
        self.url = url
        logger.info(
            f"[WebHookCallback.init] Initialized webhook callback | {{'url': '{url}'}}"
        )

    def __call__(self, response: APIResponse):
        logger.info(
            f"[WebHookCallback.call] Posting callback | {{'url': '{self.url}'}}"
        )
        post_callback(self.url, response)

    def fail(self, body):
        logger.warning(
            f"[WebHookCallback.fail] Callback failed | {{'error': '{body}'}}"
        )
        response = APIResponse.failure_response(
            error=str(body),
            metadata={"collection_job_id": str(getattr(self.collection_job, "id", ""))},
        )
        self(response)

    def success(self, body):
        logger.info("[WebHookCallback.success] Callback succeeded")
        response = APIResponse.success_response(body)
        self(response)


def _backout(crud, llm_service_id: str):
    """Best-effort cleanup: attempt to delete the assistant by ID"""
    try:
        crud.delete(llm_service_id)
    except OpenAIError as err:
        logger.error(
            f"[backout] Failed to delete resource | {{'llm_service_id': '{llm_service_id}', 'error': '{str(err)}'}}",
            exc_info=True,
        )
