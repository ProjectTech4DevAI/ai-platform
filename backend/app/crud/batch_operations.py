"""Generic batch operations orchestrator."""

import json
import logging
from io import BytesIO
from typing import Any

from sqlmodel import Session

from app.core.batch.provider_interface import BatchProvider
from app.core.cloud.storage import AmazonCloudStorageClient, SimpleStorageName
from app.crud.batch_job import (
    create_batch_job,
    update_batch_job,
)
from app.models.batch_job import BatchJob, BatchJobCreate, BatchJobUpdate

logger = logging.getLogger(__name__)


def start_batch_job(
    session: Session,
    provider: BatchProvider,
    provider_name: str,
    job_type: str,
    organization_id: int,
    project_id: int,
    jsonl_data: list[dict[str, Any]],
    config: dict[str, Any],
) -> BatchJob:
    """
    Create and start a batch job with the specified provider.

    This orchestrates the complete batch creation workflow:
    1. Create batch_job record in DB with status='pending'
    2. Call provider to upload data and create batch
    3. Update batch_job with provider IDs and status='processing'

    Args:
        session: Database session
        provider: BatchProvider instance (e.g., OpenAIBatchProvider)
        provider_name: Provider name (e.g., "openai", "anthropic")
        job_type: Job type (e.g., "evaluation", "classification")
        organization_id: Organization ID
        project_id: Project ID
        jsonl_data: List of dictionaries representing JSONL lines
        config: Complete batch configuration including provider-specific params

    Returns:
        BatchJob object with provider IDs populated

    Raises:
        Exception: If batch creation fails
    """
    logger.info(
        f"Starting {provider_name} batch job: job_type={job_type}, "
        f"org_id={organization_id}, project_id={project_id}, "
        f"items={len(jsonl_data)}"
    )

    # Step 1: Create batch_job record
    batch_job_create = BatchJobCreate(
        provider=provider_name,
        job_type=job_type,
        organization_id=organization_id,
        project_id=project_id,
        config=config,
        total_items=len(jsonl_data),
    )

    batch_job = create_batch_job(session=session, batch_job_create=batch_job_create)

    try:
        # Step 2: Call provider to create batch
        logger.info(f"Creating batch with {provider_name} provider...")
        batch_result = provider.create_batch(jsonl_data=jsonl_data, config=config)

        # Step 3: Update batch_job with provider IDs
        batch_job_update = BatchJobUpdate(
            provider_batch_id=batch_result["provider_batch_id"],
            provider_file_id=batch_result["provider_file_id"],
            provider_status=batch_result["provider_status"],
            total_items=batch_result.get("total_items", len(jsonl_data)),
        )

        batch_job = update_batch_job(
            session=session, batch_job=batch_job, batch_job_update=batch_job_update
        )

        logger.info(
            f"Successfully started batch job: id={batch_job.id}, "
            f"provider_batch_id={batch_job.provider_batch_id}"
        )

        return batch_job

    except Exception as e:
        logger.error(f"Failed to start batch job: {e}", exc_info=True)

        # Store error in batch_job (parent table will handle status)
        batch_job_update = BatchJobUpdate(
            error_message=f"Batch creation failed: {str(e)}"
        )
        update_batch_job(
            session=session, batch_job=batch_job, batch_job_update=batch_job_update
        )

        raise


def poll_batch_status(
    session: Session, provider: BatchProvider, batch_job: BatchJob
) -> dict[str, Any]:
    """
    Poll provider for batch status and update database.

    Args:
        session: Database session
        provider: BatchProvider instance
        batch_job: BatchJob object

    Returns:
        Dictionary with status information from provider

    Raises:
        Exception: If polling fails
    """
    logger.info(
        f"Polling batch status: id={batch_job.id}, "
        f"provider_batch_id={batch_job.provider_batch_id}"
    )

    try:
        # Poll provider for status
        status_result = provider.get_batch_status(batch_job.provider_batch_id)

        # Update batch_job if status changed
        provider_status = status_result["provider_status"]
        if provider_status != batch_job.provider_status:
            update_data = {"provider_status": provider_status}

            # Update output file ID if available
            if status_result.get("provider_output_file_id"):
                update_data["provider_output_file_id"] = status_result[
                    "provider_output_file_id"
                ]

            # Update error message if failed
            if status_result.get("error_message"):
                update_data["error_message"] = status_result["error_message"]

            batch_job_update = BatchJobUpdate(**update_data)
            batch_job = update_batch_job(
                session=session, batch_job=batch_job, batch_job_update=batch_job_update
            )

            logger.info(
                f"Updated batch_job {batch_job.id} status: "
                f"{batch_job.provider_status} -> {provider_status}"
            )

        return status_result

    except Exception as e:
        logger.error(f"Failed to poll batch status: {e}", exc_info=True)
        raise


def download_batch_results(
    provider: BatchProvider, batch_job: BatchJob
) -> list[dict[str, Any]]:
    """
    Download raw batch results from provider.

    Args:
        provider: BatchProvider instance
        batch_job: BatchJob object (must have provider_output_file_id)

    Returns:
        List of result dictionaries from provider

    Raises:
        ValueError: If output_file_id not available
        Exception: If download fails
    """
    if not batch_job.provider_output_file_id:
        raise ValueError(
            f"Batch job {batch_job.id} does not have provider_output_file_id"
        )

    logger.info(
        f"Downloading batch results: id={batch_job.id}, "
        f"output_file_id={batch_job.provider_output_file_id}"
    )

    try:
        results = provider.download_batch_results(batch_job.provider_output_file_id)

        logger.info(f"Downloaded {len(results)} results for batch job {batch_job.id}")

        return results

    except Exception as e:
        logger.error(f"Failed to download batch results: {e}", exc_info=True)
        raise


def process_completed_batch(
    session: Session,
    provider: BatchProvider,
    batch_job: BatchJob,
    upload_to_s3: bool = True,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Process a completed batch: download results and optionally upload to S3.

    Args:
        session: Database session
        provider: BatchProvider instance
        batch_job: BatchJob object
        upload_to_s3: Whether to upload raw results to S3

    Returns:
        Tuple of (results, s3_url)
        - results: List of result dictionaries
        - s3_url: S3 URL if uploaded, None otherwise

    Raises:
        Exception: If processing fails
    """
    logger.info(f"Processing completed batch: id={batch_job.id}")

    try:
        # Download results
        results = download_batch_results(provider=provider, batch_job=batch_job)

        # Upload to S3 if requested
        s3_url = None
        if upload_to_s3:
            try:
                s3_url = upload_batch_results_to_s3(
                    batch_job=batch_job, results=results
                )
                logger.info(f"Uploaded batch results to S3: {s3_url}")
            except Exception as s3_error:
                logger.warning(
                    f"S3 upload failed (AWS credentials may not be configured): {s3_error}. "
                    f"Continuing without S3 storage.",
                    exc_info=True,
                )

        # Update batch_job with S3 URL
        if s3_url:
            batch_job_update = BatchJobUpdate(raw_output_url=s3_url)
            update_batch_job(
                session=session, batch_job=batch_job, batch_job_update=batch_job_update
            )

        return results, s3_url

    except Exception as e:
        logger.error(f"Failed to process completed batch: {e}", exc_info=True)
        raise


def upload_batch_results_to_s3(
    batch_job: BatchJob, results: list[dict[str, Any]]
) -> str:
    """
    Upload batch results to S3.

    Args:
        batch_job: BatchJob object
        results: List of result dictionaries

    Returns:
        S3 URL

    Raises:
        Exception: If upload fails
    """
    logger.info(f"Uploading batch results to S3 for batch_job {batch_job.id}")

    try:
        # Create S3 key path
        # Format: {job_type}/batch-{id}/results.jsonl
        s3_key = f"{batch_job.job_type}/batch-{batch_job.id}/results.jsonl"

        # Convert results to JSONL
        jsonl_content = "\n".join([json.dumps(result) for result in results])
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
            f"Successfully uploaded batch results to S3: {s3_url} ({len(content_bytes)} bytes)"
        )

        return s3_url

    except Exception as e:
        logger.error(f"Failed to upload batch results to S3: {e}", exc_info=True)
        raise


# NOTE: Batch-level polling has been removed from this module.
# Polling should be done at the parent table level (e.g., evaluation_run)
# because only the parent knows when its business logic is complete.
#
# For example:
# - poll_all_pending_evaluations() in evaluation_processing.py
# - poll_all_pending_classifications() in classification_processing.py (future)
#
# Each parent-specific polling function should:
# 1. Query parent table for status="processing"
# 2. Poll batch_job.provider_status via poll_batch_status()
# 3. Update parent table status based on business logic
