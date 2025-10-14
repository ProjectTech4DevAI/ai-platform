"""
Evaluation batch processing orchestrator.

This module coordinates the complete evaluation workflow:
1. Polling batch status from OpenAI
2. Downloading and parsing completed batch results
3. Uploading results to S3
4. Creating Langfuse dataset runs with traces
5. Updating database with final status
"""

import logging
from typing import Any

from langfuse import Langfuse
from openai import OpenAI
from sqlmodel import Session

from app.core.util import configure_langfuse, configure_openai, now
from app.crud.credentials import get_provider_credential
from app.crud.evaluation_batch import (
    download_batch_output,
    fetch_dataset_items,
    get_pending_evaluations,
    parse_batch_output,
    poll_batch_status,
    upload_results_to_s3,
)
from app.crud.evaluation_langfuse import create_langfuse_dataset_run
from app.models import EvaluationRun

logger = logging.getLogger(__name__)


async def process_completed_batch(
    eval_run: EvaluationRun,
    session: Session,
    openai_client: OpenAI,
    langfuse: Langfuse,
    output_file_id: str,
) -> EvaluationRun:
    """
    Process a completed batch evaluation.

    This function:
    1. Downloads batch output from OpenAI
    2. Parses results into question/output/ground_truth format
    3. Uploads results to S3
    4. Creates Langfuse dataset run with traces
    5. Updates database with completion status

    Args:
        eval_run: EvaluationRun database object
        session: Database session
        openai_client: Configured OpenAI client
        langfuse: Configured Langfuse client
        output_file_id: OpenAI file ID for batch output

    Returns:
        Updated EvaluationRun object

    Raises:
        Exception: If processing fails
    """
    logger.info(f"Processing completed batch for evaluation run {eval_run.id}")

    try:
        # Step 1: Download batch output from OpenAI
        logger.info(f"Step 1: Downloading batch output file: {output_file_id}")
        jsonl_content = download_batch_output(
            client=openai_client, output_file_id=output_file_id
        )

        # Step 2: Fetch dataset items (needed for matching ground truth)
        logger.info(f"Step 2: Fetching dataset items for '{eval_run.dataset_name}'")
        dataset_items = fetch_dataset_items(
            langfuse=langfuse, dataset_name=eval_run.dataset_name
        )

        # Step 3: Parse batch output into structured results
        logger.info("Step 3: Parsing batch output")
        results = parse_batch_output(
            jsonl_content=jsonl_content, dataset_items=dataset_items
        )

        if not results:
            raise ValueError("No valid results found in batch output")

        # Step 4: Upload results to S3
        logger.info("Step 4: Uploading results to S3")
        s3_url = upload_results_to_s3(
            jsonl_content=jsonl_content,
            eval_run=eval_run,
            project_id=eval_run.project_id,
        )

        # Step 5: Update DB with output file ID and S3 URL
        logger.info("Step 5: Updating database with S3 URL")
        eval_run.batch_output_file_id = output_file_id
        eval_run.s3_url = s3_url
        eval_run.updated_at = now()
        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)

        # Step 6: Create Langfuse dataset run with traces
        logger.info("Step 6: Creating Langfuse dataset run with traces")
        create_langfuse_dataset_run(
            langfuse=langfuse,
            dataset_name=eval_run.dataset_name,
            run_name=eval_run.run_name,
            results=results,
        )

        # Step 7: Mark as completed
        logger.info("Step 7: Marking evaluation as completed")
        eval_run.status = "completed"
        eval_run.updated_at = now()
        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)

        logger.info(
            f"Successfully completed processing for evaluation run {eval_run.id}: "
            f"{len(results)} items processed, S3 URL: {s3_url}"
        )

        return eval_run

    except Exception as e:
        logger.error(
            f"Failed to process completed batch for run {eval_run.id}: {e}",
            exc_info=True,
        )
        # Mark as failed
        eval_run.status = "failed"
        eval_run.error_message = f"Processing failed: {str(e)}"
        eval_run.updated_at = now()
        session.add(eval_run)
        session.commit()
        raise


async def check_and_process_batch(
    eval_run: EvaluationRun,
    session: Session,
    openai_client: OpenAI,
    langfuse: Langfuse,
) -> dict[str, Any]:
    """
    Check batch status and process if completed.

    Args:
        eval_run: EvaluationRun database object
        session: Database session
        openai_client: Configured OpenAI client
        langfuse: Configured Langfuse client

    Returns:
        Dict with status information:
        {
            "run_id": 123,
            "run_name": "test_run",
            "previous_status": "processing",
            "current_status": "completed",
            "batch_status": "completed",
            "action": "processed" | "updated" | "failed" | "no_change"
        }
    """
    logger.info(
        f"Checking batch status for evaluation run {eval_run.id} (batch_id={eval_run.batch_id})"
    )

    previous_status = eval_run.status
    previous_batch_status = eval_run.batch_status

    try:
        # Poll batch status from OpenAI
        batch_status_info = poll_batch_status(
            client=openai_client, batch_id=eval_run.batch_id
        )

        new_batch_status = batch_status_info["status"]
        output_file_id = batch_status_info.get("output_file_id")

        # Update batch status in DB
        if new_batch_status != previous_batch_status:
            eval_run.batch_status = new_batch_status
            eval_run.updated_at = now()
            session.add(eval_run)
            session.commit()
            session.refresh(eval_run)
            logger.info(
                f"Updated batch_status for run {eval_run.id}: "
                f"{previous_batch_status} -> {new_batch_status}"
            )

        # Handle different batch statuses
        if new_batch_status == "completed":
            if not output_file_id:
                raise ValueError("Batch completed but no output_file_id found")

            logger.info(f"Batch {eval_run.batch_id} completed, processing results...")

            # Process the completed batch
            await process_completed_batch(
                eval_run=eval_run,
                session=session,
                openai_client=openai_client,
                langfuse=langfuse,
                output_file_id=output_file_id,
            )

            return {
                "run_id": eval_run.id,
                "run_name": eval_run.run_name,
                "previous_status": previous_status,
                "current_status": eval_run.status,
                "batch_status": new_batch_status,
                "action": "processed",
            }

        elif new_batch_status in ["failed", "expired", "cancelled"]:
            # Mark as failed
            error_msg = f"Batch {new_batch_status}"
            if batch_status_info.get("error_file_id"):
                error_msg += f" (error_file_id: {batch_status_info['error_file_id']})"

            eval_run.status = "failed"
            eval_run.error_message = error_msg
            eval_run.updated_at = now()
            session.add(eval_run)
            session.commit()
            session.refresh(eval_run)

            logger.error(f"Batch {eval_run.batch_id} failed: {error_msg}")

            return {
                "run_id": eval_run.id,
                "run_name": eval_run.run_name,
                "previous_status": previous_status,
                "current_status": "failed",
                "batch_status": new_batch_status,
                "action": "failed",
                "error": error_msg,
            }

        else:
            # Still in progress (validating, in_progress, finalizing)
            logger.info(
                f"Batch {eval_run.batch_id} still processing (status={new_batch_status})"
            )

            return {
                "run_id": eval_run.id,
                "run_name": eval_run.run_name,
                "previous_status": previous_status,
                "current_status": eval_run.status,
                "batch_status": new_batch_status,
                "action": "updated"
                if new_batch_status != previous_batch_status
                else "no_change",
            }

    except Exception as e:
        logger.error(
            f"Error checking batch status for run {eval_run.id}: {e}", exc_info=True
        )

        # Mark as failed
        eval_run.status = "failed"
        eval_run.error_message = f"Polling failed: {str(e)}"
        eval_run.updated_at = now()
        session.add(eval_run)
        session.commit()

        return {
            "run_id": eval_run.id,
            "run_name": eval_run.run_name,
            "previous_status": previous_status,
            "current_status": "failed",
            "batch_status": eval_run.batch_status,
            "action": "failed",
            "error": str(e),
        }


async def poll_all_pending_evaluations(session: Session, org_id: int) -> dict[str, Any]:
    """
    Poll all pending evaluations for an organization.

    Args:
        session: Database session
        org_id: Organization ID

    Returns:
        Summary dict:
        {
            "total": 5,
            "processed": 2,
            "failed": 1,
            "still_processing": 2,
            "details": [...]
        }
    """
    logger.info(f"Polling all pending evaluations for org_id={org_id}")

    # Get pending evaluations
    pending_runs = get_pending_evaluations(session=session)

    # Filter by org_id
    pending_runs = [run for run in pending_runs if run.organization_id == org_id]

    if not pending_runs:
        logger.info(f"No pending evaluations found for org_id={org_id}")
        return {
            "total": 0,
            "processed": 0,
            "failed": 0,
            "still_processing": 0,
            "details": [],
        }

    logger.info(f"Found {len(pending_runs)} pending evaluations for org_id={org_id}")

    # Get credentials
    openai_credentials = get_provider_credential(
        session=session, org_id=org_id, provider="openai"
    )
    langfuse_credentials = get_provider_credential(
        session=session, org_id=org_id, provider="langfuse"
    )

    if not openai_credentials or not langfuse_credentials:
        logger.error(
            f"Missing credentials for org_id={org_id}: "
            f"openai={bool(openai_credentials)}, langfuse={bool(langfuse_credentials)}"
        )
        return {
            "total": len(pending_runs),
            "processed": 0,
            "failed": 0,
            "still_processing": len(pending_runs),
            "details": [],
            "error": "Missing OpenAI or Langfuse credentials",
        }

    # Configure clients
    openai_client, openai_success = configure_openai(openai_credentials)
    langfuse, langfuse_success = configure_langfuse(langfuse_credentials)

    if not openai_success or not langfuse_success:
        logger.error(f"Failed to configure clients for org_id={org_id}")
        return {
            "total": len(pending_runs),
            "processed": 0,
            "failed": 0,
            "still_processing": len(pending_runs),
            "details": [],
            "error": "Failed to configure API clients",
        }

    # Process each evaluation
    results = []
    processed_count = 0
    failed_count = 0
    still_processing_count = 0

    for eval_run in pending_runs:
        try:
            result = await check_and_process_batch(
                eval_run=eval_run,
                session=session,
                openai_client=openai_client,
                langfuse=langfuse,
            )
            results.append(result)

            if result["action"] == "processed":
                processed_count += 1
            elif result["action"] == "failed":
                failed_count += 1
            else:
                still_processing_count += 1

        except Exception as e:
            logger.error(
                f"Failed to check evaluation run {eval_run.id}: {e}", exc_info=True
            )
            results.append(
                {
                    "run_id": eval_run.id,
                    "run_name": eval_run.run_name,
                    "action": "failed",
                    "error": str(e),
                }
            )
            failed_count += 1

    summary = {
        "total": len(pending_runs),
        "processed": processed_count,
        "failed": failed_count,
        "still_processing": still_processing_count,
        "details": results,
    }

    logger.info(
        f"Polling summary for org_id={org_id}: "
        f"{processed_count} processed, {failed_count} failed, "
        f"{still_processing_count} still processing"
    )

    return summary
