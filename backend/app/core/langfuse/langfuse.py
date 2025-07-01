import uuid
import logging
from typing import Any, Dict, Optional

from langfuse import Langfuse
from langfuse.client import StatefulGenerationClient, StatefulTraceClient

logger = logging.getLogger(__name__)


class LangfuseTracer:
    def __init__(
        self,
        credentials: Optional[dict] = None,
        session_id: Optional[str] = None,
        response_id: Optional[str] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.langfuse: Optional[Langfuse] = None
        self.trace: Optional[StatefulTraceClient] = None
        self.generation: Optional[StatefulGenerationClient] = None

        has_credentials = (
            credentials
            and "public_key" in credentials
            and "secret_key" in credentials
            and "host" in credentials
        )

        if has_credentials:
            self.langfuse = Langfuse(
                public_key=credentials["public_key"],
                secret_key=credentials["secret_key"],
                host=credentials["host"],
                enabled=True,  # This ensures the client is active
            )

            if response_id:
                traces = self.langfuse.fetch_traces(tags=response_id).data
                if traces:
                    self.session_id = traces[0].session_id

            logger.info(
                f"[LangfuseTracer] Langfuse tracing enabled | session_id={self.session_id}"
            )
        else:
            self.langfuse = Langfuse(enabled=False)
            logger.warning(
                "[LangfuseTracer] Langfuse tracing disabled due to missing credentials"
            )

    def start_trace(
        self,
        name: str,
        input: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.trace = self.langfuse.trace(
            name=name,
            input=input,
            metadata=metadata or {},
            session_id=self.session_id,
        )

    def start_generation(
        self,
        name: str,
        input: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self.trace:
            return
        self.generation = self.langfuse.generation(
            name=name,
            trace_id=self.trace.id,
            input=input,
            metadata=metadata or {},
        )

    def end_generation(
        self,
        output: Dict[str, Any],
        usage: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ):
        if self.generation:
            self.generation.end(output=output, usage=usage, model=model)

    def update_trace(self, tags: list[str], output: Dict[str, Any]):
        if self.trace:
            self.trace.update(tags=tags, output=output)

    def log_error(self, error_message: str, response_id: Optional[str] = None):
        if self.generation:
            self.generation.end(output={"error": error_message})
        if self.trace:
            self.trace.update(
                tags=[response_id] if response_id else [],
                output={"status": "failure", "error": error_message},
            )

    def flush(self):
        self.langfuse.flush()
