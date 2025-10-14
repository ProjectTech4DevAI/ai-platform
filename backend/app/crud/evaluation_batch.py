"""
OpenAI Batch API integration for LLM evaluations using Responses API.

This module handles:
1. Fetching dataset items from Langfuse
2. Building JSONL for OpenAI Batch API (/v1/responses endpoint)
3. Uploading and creating batch jobs
"""

import json
import logging
from typing import Any

from langfuse import Langfuse
from openai import OpenAI
from sqlmodel import Session

from app.models import EvaluationRun

logger = logging.getLogger(__name__)


def fetch_dataset_items(langfuse: Langfuse, dataset_name: str) -> list[dict[str, Any]]:
    """
    Fetch all items from a Langfuse dataset.

    Args:
        langfuse: Configured Langfuse client
        dataset_name: Name of the dataset to fetch

    Returns:
        List of dataset items with input and expected_output

    Raises:
        ValueError: If dataset not found or empty
    """
    logger.info(f"Fetching dataset: {dataset_name}")

    try:
        dataset = langfuse.get_dataset(dataset_name)
    except Exception as e:
        logger.error(f"Failed to fetch dataset '{dataset_name}': {e}")
        raise ValueError(f"Dataset '{dataset_name}' not found: {e}")

    if not dataset.items:
        raise ValueError(f"Dataset '{dataset_name}' is empty")

    items = []
    for item in dataset.items:
        items.append(
            {
                "id": item.id,
                "input": item.input,
                "expected_output": item.expected_output,
                "metadata": item.metadata if hasattr(item, "metadata") else {},
            }
        )

    logger.info(f"Fetched {len(items)} items from dataset '{dataset_name}'")
    return items


def build_batch_jsonl(
    dataset_items: list[dict[str, Any]], config: dict[str, Any]
) -> list[str]:
    """
    Build JSONL lines for OpenAI Batch API using Responses API.

    Each line is a JSON object with:
    - custom_id: Unique identifier for the request
    - method: POST
    - url: /v1/responses
    - body: Response request with model, instructions, and input

    Args:
        dataset_items: List of dataset items from Langfuse
        config: Evaluation configuration dict with llm, instructions, vector_store_ids

    Returns:
        List of JSONL strings (one per dataset item)
    """
    # Extract config values
    llm_config = config.get("llm", {})
    model = llm_config.get("model", "gpt-4o")
    instructions = config.get("instructions", "You are a helpful assistant")
    vector_store_ids = config.get("vector_store_ids", [])

    logger.info(f"Building JSONL for {len(dataset_items)} items with model {model}")

    batch_file = []

    for item in dataset_items:
        # Extract question from input
        question = item["input"].get("question", "")
        if not question:
            logger.warning(f"Skipping item {item['id']} - no question found")
            continue

        # Build the batch request object for Responses API
        batch_request = {
            "custom_id": item["id"],
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": model,
                "instructions": instructions,
                "input": question,
            },
        }

        # Add vector store IDs if available (for file search)
        if vector_store_ids:
            batch_request["body"]["tools"] = [{"type": "file_search"}]
            batch_request["body"]["tool_choice"] = "auto"

        batch_file.append(json.dumps(batch_request))

    logger.info(f"Built {len(batch_file)} JSONL lines")
    return batch_file


def upload_batch_file(client: OpenAI, batch_file: list[str]) -> str:
    """
    Upload JSONL content to OpenAI Files API.

    Args:
        client: Configured OpenAI client
        batch_file: List of JSONL strings

    Returns:
        File ID from OpenAI

    Raises:
        Exception: If upload fails
    """
    logger.info(f"Uploading {len(batch_file)} lines to OpenAI Files API")

    # Join lines with newlines
    jsonl_content = "\n".join(batch_file)

    try:
        # Upload as a file object
        file_response = client.files.create(
            file=("batch_input.jsonl", jsonl_content.encode("utf-8")),
            purpose="batch",
        )

        logger.info(f"Uploaded file: {file_response.id}")
        return file_response.id

    except Exception as e:
        logger.error(f"Failed to upload batch file: {e}")
        raise


def create_batch_job(
    client: OpenAI,
    file_id: str,
    description: str = "LLM evaluation batch",
) -> dict[str, Any]:
    """
    Create a batch job in OpenAI using Responses API.

    Args:
        client: Configured OpenAI client
        file_id: File ID from upload_batch_file
        description: Optional description for the batch

    Returns:
        Dict with batch details (id, status, etc.)

    Raises:
        Exception: If batch creation fails
    """
    logger.info(f"Creating batch job with file: {file_id}")

    try:
        batch = client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/responses",
            completion_window="24h",
            metadata={"description": description},
        )

        batch_info = {
            "id": batch.id,
            "status": batch.status,
            "created_at": batch.created_at,
            "endpoint": batch.endpoint,
            "input_file_id": batch.input_file_id,
        }

        logger.info(f"Created batch: {batch.id} (status={batch.status})")
        return batch_info

    except Exception as e:
        logger.error(f"Failed to create batch job: {e}")
        raise


def start_evaluation_batch(
    langfuse: Langfuse,
    openai_client: OpenAI,
    session: Session,
    eval_run: EvaluationRun,
    config: dict[str, Any],
) -> EvaluationRun:
    """
    Fetch data, build JSONL, upload to OpenAI, create batch.

    Args:
        langfuse: Configured Langfuse client
        openai_client: Configured OpenAI client
        session: Database session
        eval_run: EvaluationRun database object (with run_name, dataset_name, config)
        config: Evaluation configuration dict with llm, instructions, vector_store_ids

    Returns:
        Updated EvaluationRun with batch_id and batch_file_id populated

    Raises:
        Exception: If any step fails
    """
    try:
        # Step 1: Fetch dataset items from Langfuse
        dataset_items = fetch_dataset_items(
            langfuse=langfuse, dataset_name=eval_run.dataset_name
        )

        # Step 2: Build JSONL using config
        batch_file = build_batch_jsonl(dataset_items=dataset_items, config=config)

        # Step 3: Upload to OpenAI
        file_id = upload_batch_file(client=openai_client, batch_file=batch_file)

        # Step 4: Create batch job
        batch_info = create_batch_job(
            client=openai_client,
            file_id=file_id,
            description=f"Evaluation: {eval_run.run_name}",
        )

        # Update eval_run with batch info
        eval_run.batch_id = batch_info["id"]
        eval_run.batch_file_id = file_id
        eval_run.batch_status = batch_info[
            "status"
        ]  # OpenAI batch status (e.g., "validating")
        eval_run.total_items = len(batch_file)
        eval_run.status = "processing"  # Overall evaluation status

        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)

        logger.info(
            f"Successfully started evaluation batch: {batch_info['id']} "
            f"for run '{eval_run.run_name}' with {len(batch_file)} items"
        )

        return eval_run

    except Exception as e:
        logger.error(f"Failed to start evaluation batch: {e}", exc_info=True)
        eval_run.status = "failed"
        eval_run.error_message = str(e)
        session.add(eval_run)
        session.commit()
        raise
