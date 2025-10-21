"""LLM response models.

This module contains response models for LLM API calls.
"""
from sqlmodel import SQLModel


class LLMCallResponse(SQLModel):
    """Response model for /v1/llm/call endpoint.

    Attributes:
        status: Response status (success, error, etc.)
        response_id: Unique identifier for this response
        message: The generated text response
        model: Model identifier that was used
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens generated
        total_tokens: Total tokens consumed (input + output)
        file_search_results: Optional list of file search results from RAG
    """

    status: str
    response_id: str
    message: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
