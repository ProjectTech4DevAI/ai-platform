"""LLM response models.

This module contains response models for LLM API calls.
"""
from sqlmodel import SQLModel, Field


class Diagnostics(SQLModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    provider: str


class LLMCallResponse(SQLModel):
    id: str = Field(..., description="Unique id provided by the LLM provider.")
    conversation_id: str | None = None
    output: str
    usage: Diagnostics
    llm_response: dict | None = Field(
        default=None, description="Raw Response from LLM provider."
    )
