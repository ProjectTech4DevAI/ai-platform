"""Generic batch operations orchestrator."""

import logging
from typing import Any

from sqlmodel import Session

from app.core.batch.provider_interface import BatchProvider
from app.core.cloud import get_cloud_storage
from app.core.storage_utils import upload_jsonl_to_object_store as shared_upload_jsonl
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
        f"[start_batch_job] Starting batch job | provider={provider_name} | "
        f"job_type={job_type} | org_id={organization_id} | project_id={project_id} | "
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
        logger.info(
            f"[start_batch_job] Creating batch with provider | provider={provider_name}"
        )
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
            f"[start_batch_job] Successfully started batch job | id={batch_job.id} | "
            f"provider_batch_id={batch_job.provider_batch_id}"
        )

        return batch_job

    except Exception as e:
        logger.error(
            f"[start_batch_job] Failed to start batch job | {e}", exc_info=True
        )

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
        f"[poll_batch_status] Polling batch status | id={batch_job.id} | "
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
                f"[poll_batch_status] Updated batch_job status | id={batch_job.id} | "
                f"{batch_job.provider_status} -> {provider_status}"
            )

        return status_result

    except Exception as e:
        logger.error(
            f"[poll_batch_status] Failed to poll batch status | {e}", exc_info=True
        )
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
        f"[download_batch_results] Downloading batch results | id={batch_job.id} | "
        f"output_file_id={batch_job.provider_output_file_id}"
    )

    try:
        results = provider.download_batch_results(batch_job.provider_output_file_id)

        logger.info(
            f"[download_batch_results] Downloaded results | batch_job_id={batch_job.id} | results={len(results)}"
        )

        return results

    except Exception as e:
        logger.error(
            f"[download_batch_results] Failed to download batch results | {e}",
            exc_info=True,
        )
        raise


def process_completed_batch(
    session: Session,
    provider: BatchProvider,
    batch_job: BatchJob,
    upload_to_object_store: bool = True,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Process a completed batch: download results and optionally upload to object store.

    Args:
        session: Database session
        provider: BatchProvider instance
        batch_job: BatchJob object
        upload_to_object_store: Whether to upload raw results to object store

    Returns:
        Tuple of (results, object_store_url)
        - results: List of result dictionaries
        - object_store_url: Object store URL if uploaded, None otherwise

    Raises:
        Exception: If processing fails
    """
    logger.info(
        f"[process_completed_batch] Processing completed batch | id={batch_job.id}"
    )

    try:
        # Download results
        results = download_batch_results(provider=provider, batch_job=batch_job)

        # Upload to object store if requested
        object_store_url = None
        if upload_to_object_store:
            try:
                object_store_url = upload_batch_results_to_object_store(
                    session=session, batch_job=batch_job, results=results
                )
                logger.info(
                    f"[process_completed_batch] Uploaded batch results to object store | {object_store_url}"
                )
            except Exception as store_error:
                logger.warning(
                    f"[process_completed_batch] Object store upload failed (credentials may not be configured) | "
                    f"{store_error} | Continuing without object store storage",
                    exc_info=True,
                )

        # Update batch_job with object store URL
        if object_store_url:
            batch_job_update = BatchJobUpdate(raw_output_url=object_store_url)
            update_batch_job(
                session=session, batch_job=batch_job, batch_job_update=batch_job_update
            )

        return results, object_store_url

    except Exception as e:
        logger.error(
            f"[process_completed_batch] Failed to process completed batch | {e}",
            exc_info=True,
        )
        raise


def upload_batch_results_to_object_store(
    session: Session, batch_job: BatchJob, results: list[dict[str, Any]]
) -> str | None:
    """
    Upload batch results to object store.

    This function uses the shared storage utility for consistent upload behavior.

    Args:
        session: Database session (for getting cloud storage)
        batch_job: BatchJob object
        results: List of result dictionaries

    Returns:
        Object store URL if successful, None if failed

    Raises:
        Exception: If upload fails
    """
    logger.info(
        f"[upload_batch_results_to_object_store] Uploading batch results to object store | batch_job_id={batch_job.id}"
    )

    try:
        # Get cloud storage instance
        storage = get_cloud_storage(session=session, project_id=batch_job.project_id)

        # Define subdirectory and filename
        # Format: {job_type}/batch-{id}/results.jsonl
        subdirectory = f"{batch_job.job_type}/batch-{batch_job.id}"
        filename = "results.jsonl"

        # Use shared utility for upload
        object_store_url = shared_upload_jsonl(
            storage=storage,
            results=results,
            filename=filename,
            subdirectory=subdirectory,
        )

        return object_store_url

    except Exception as e:
        logger.error(
            f"[upload_batch_results_to_object_store] Failed to upload batch results to object store | {e}",
            exc_info=True,
        )
        raise


# Backward compatibility alias
upload_batch_results_to_s3 = upload_batch_results_to_object_store


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
