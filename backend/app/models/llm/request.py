"""LLM request models.

This module contains request models for LLM API calls.
"""

from sqlmodel import SQLModel

from app.models.llm.config import LLMConfig


class LLMCallRequest(SQLModel):
    """Request model for /v1/llm/call endpoint.

    This model decouples LLM calls from the assistants table,
    allowing dynamic configuration per request.

    Attributes:
        llm: LLM configuration containing model spec and prompt
        max_num_results: Number of results to return from vector store file search
    """

    llm: LLMConfig
    max_num_results: int = 20  # For vector store file search
