"""
OpenAI Batch API integration for LLM evaluations using Responses API.

This module handles:
1. Fetching dataset items from Langfuse
2. Building JSONL for OpenAI Batch API (/v1/responses endpoint)
3. Uploading and creating batch jobs
4. Polling batch status and downloading results
"""

import json
import logging
from typing import Any

from langfuse import Langfuse
from openai import OpenAI
from sqlmodel import Session, select

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
        # Only add tools if vector_store_ids is a non-empty list
        if vector_store_ids and len(vector_store_ids) > 0:
            batch_request["body"]["tools"] = [
                {
                    "type": "file_search",
                    "vector_store_ids": vector_store_ids,
                }
            ]
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


# ============================================================================
# Batch Polling and Result Processing
# ============================================================================


def get_pending_evaluations(session: Session) -> list[EvaluationRun]:
    """
    Get all evaluations that are currently processing and need polling.

    Args:
        session: Database session

    Returns:
        List of EvaluationRun objects with status='processing'
    """
    statement = select(EvaluationRun).where(EvaluationRun.status == "processing")
    results = session.exec(statement).all()
    logger.info(f"Found {len(results)} evaluations in 'processing' status")
    return list(results)


def poll_batch_status(client: OpenAI, batch_id: str) -> dict[str, Any]:
    """
    Poll OpenAI for current batch status.

    Args:
        client: Configured OpenAI client
        batch_id: Batch ID to poll

    Returns:
        Dict with batch status information:
        {
            "id": "batch_abc123",
            "status": "completed" | "failed" | "in_progress" | "validating" | ...,
            "output_file_id": "file-xyz" (if completed),
            "error_file_id": "file-err" (if failed),
            "failed_requests": 0,
            "completed_requests": 10,
            "total_requests": 10
        }

    Raises:
        Exception: If polling fails
    """
    logger.info(f"Polling batch status: {batch_id}")

    try:
        batch = client.batches.retrieve(batch_id)

        batch_status = {
            "id": batch.id,
            "status": batch.status,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id,
            "request_counts": {
                "total": batch.request_counts.total,
                "completed": batch.request_counts.completed,
                "failed": batch.request_counts.failed,
            },
        }

        logger.info(
            f"Batch {batch_id} status: {batch.status} "
            f"({batch.request_counts.completed}/{batch.request_counts.total} completed), "
            f"output_file_id={batch.output_file_id}, error_file_id={batch.error_file_id}"
        )

        return batch_status

    except Exception as e:
        logger.error(f"Failed to poll batch status for {batch_id}: {e}")
        raise


def download_batch_output(client: OpenAI, output_file_id: str) -> str:
    """
    Download batch output JSONL from OpenAI.

    Args:
        client: Configured OpenAI client
        output_file_id: File ID of the batch output

    Returns:
        JSONL content as string

    Raises:
        Exception: If download fails
    """
    logger.info(f"Downloading batch output file: {output_file_id}")

    try:
        file_content = client.files.content(output_file_id)
        jsonl_content = file_content.read().decode("utf-8")

        # Count lines for logging
        line_count = len(jsonl_content.strip().split("\n"))
        logger.info(f"Downloaded {line_count} lines from output file {output_file_id}")

        return jsonl_content

    except Exception as e:
        logger.error(f"Failed to download batch output {output_file_id}: {e}")
        raise


def extract_output_text(output: list[dict[str, Any]]) -> str:
    """
    Extract clean text from Response API output array.

    This mimics the logic from OpenAI SDK's Response.output_text property.
    The output array contains items with different types (message, file_search_call, etc.).
    We extract text from message items that contain output_text content blocks.

    Args:
        output: The output array from the Response API
                Format: [
                    {"type": "file_search_call", ...},
                    {"type": "message", "content": [{"type": "output_text", "text": "..."}]}
                ]

    Returns:
        Extracted text string, or empty string if no text found
    """
    texts = []

    for output_item in output:
        # Look for message type items (similar to SDK logic)
        if isinstance(output_item, dict) and output_item.get("type") == "message":
            content = output_item.get("content", [])

            if isinstance(content, list):
                for content_item in content:
                    if (
                        isinstance(content_item, dict)
                        and content_item.get("type") == "output_text"
                    ):
                        text = content_item.get("text", "")
                        if text:
                            texts.append(text)

    return "".join(texts)


def parse_batch_output(
    jsonl_content: str, dataset_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Parse batch output JSONL into structured results.

    Args:
        jsonl_content: Raw JSONL string from OpenAI batch output
        dataset_items: Original dataset items (for matching ground truth)

    Returns:
        List of results in format:
        [
            {
                "item_id": "item_123",
                "question": "What is 2+2?",
                "generated_output": "4",
                "ground_truth": "4"
            },
            ...
        ]
    """
    logger.info("Parsing batch output JSONL")

    # Create lookup map for dataset items by ID
    dataset_map = {item["id"]: item for item in dataset_items}

    results = []
    lines = jsonl_content.strip().split("\n")

    for line_num, line in enumerate(lines, 1):
        try:
            response = json.loads(line)

            # Extract custom_id (which is our dataset item ID)
            item_id = response.get("custom_id")
            if not item_id:
                logger.warning(f"Line {line_num}: No custom_id found, skipping")
                continue

            # Get original dataset item
            dataset_item = dataset_map.get(item_id)
            if not dataset_item:
                logger.warning(f"Line {line_num}: No dataset item found for {item_id}")
                continue

            # Extract the response body
            response_body = response.get("response", {}).get("body", {})

            # Handle errors in batch processing
            if response.get("error"):
                error_msg = response["error"].get("message", "Unknown error")
                logger.error(f"Item {item_id} had error: {error_msg}")
                generated_output = f"ERROR: {error_msg}"
            else:
                # Extract output text from response
                # Response API can return simple string or complex array structure
                output = response_body.get("output", [])

                # If output is a string, check if it's a stringified list/dict
                if isinstance(output, str):
                    # Try to parse it as JSON first (in case it's a JSON string)
                    try:
                        # Try JSON parsing (for properly escaped strings)
                        parsed_output = json.loads(output)
                        if isinstance(parsed_output, list):
                            generated_output = extract_output_text(parsed_output)
                        else:
                            generated_output = output
                    except (json.JSONDecodeError, ValueError):
                        # If JSON parsing fails, try literal_eval for Python string representation
                        try:
                            import ast

                            parsed_output = ast.literal_eval(output)
                            if isinstance(parsed_output, list):
                                generated_output = extract_output_text(parsed_output)
                            else:
                                generated_output = output
                        except (ValueError, SyntaxError):
                            # If both fail, use the string as-is
                            generated_output = output
                # If output is a list (complex structure), extract text from message items
                elif isinstance(output, list):
                    generated_output = extract_output_text(output)
                else:
                    generated_output = ""
                    logger.warning(
                        f"Item {item_id}: Unexpected output type: {type(output)}"
                    )

                # Log the extracted output for debugging
                logger.debug(
                    f"Item {item_id}: Extracted clean text output "
                    f"(length={len(generated_output)}, preview={generated_output[:100]}...)"
                )

            # Extract question and ground truth from dataset item
            question = dataset_item["input"].get("question", "")
            ground_truth = dataset_item["expected_output"].get("answer", "")

            results.append(
                {
                    "item_id": item_id,
                    "question": question,
                    "generated_output": generated_output,
                    "ground_truth": ground_truth,
                }
            )

        except json.JSONDecodeError as e:
            logger.error(f"Line {line_num}: Failed to parse JSON: {e}")
            continue
        except Exception as e:
            logger.error(f"Line {line_num}: Unexpected error: {e}")
            continue

    logger.info(f"Parsed {len(results)} results from {len(lines)} output lines")
    return results


def upload_results_to_s3(
    jsonl_content: str, eval_run: EvaluationRun, project_id: int
) -> str:
    """
    Upload evaluation results to S3.

    Args:
        jsonl_content: JSONL content to upload
        eval_run: EvaluationRun database object
        project_id: Project ID for storage path

    Returns:
        S3 URL (e.g., s3://bucket/project-uuid/evaluations/run-123/results.jsonl)

    Raises:
        Exception: If upload fails
    """
    from io import BytesIO
    from app.core.cloud.storage import (
        AmazonCloudStorageClient,
        SimpleStorageName,
    )

    logger.info(f"Uploading results to S3 for evaluation run {eval_run.id}")

    try:
        # Create S3 key path
        # Format: project-storage-path/evaluations/run-{id}/results.jsonl
        s3_key = f"evaluations/run-{eval_run.id}/results.jsonl"

        # Convert string content to bytes
        content_bytes = jsonl_content.encode("utf-8")
        file_like = BytesIO(content_bytes)

        # Upload to S3
        aws_client = AmazonCloudStorageClient()
        aws_client.client.upload_fileobj(
            file_like,
            Bucket=aws_client.client._client_config.__dict__.get(
                "bucket", "kaapi-storage"
            ),
            Key=s3_key,
            ExtraArgs={"ContentType": "application/jsonl"},
        )

        # Construct S3 URL
        storage_name = SimpleStorageName(Key=s3_key)
        s3_url = str(storage_name)

        logger.info(
            f"Successfully uploaded results to S3: {s3_url} "
            f"({len(content_bytes)} bytes)"
        )

        return s3_url

    except Exception as e:
        logger.error(f"Failed to upload results to S3: {e}", exc_info=True)
        raise
