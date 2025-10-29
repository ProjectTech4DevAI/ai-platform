"""LLM response models.

This module contains response models for LLM API calls.
"""
from sqlmodel import SQLModel, Field


class Usage(SQLModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


# class LLMOutput(SQLModel):
#     text: str = Field(..., description="Primary text content of the LLM response.")


class LLMCallResponse(SQLModel):
    id: str = Field(..., description="Unique id provided by the LLM provider.")
    conversation_id: str | None = None
    # output: LLMOutput = Field(..., description="Structured output containing text and other data.")
    output: str = Field(..., description="Primary text content of the LLM response.")
    model: str
    provider: str
    usage: Usage
    provider_raw_response: dict | None = Field(
        default=None, description="Raw Response from LLM provider."
    )
