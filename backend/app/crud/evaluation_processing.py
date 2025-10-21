"""
Evaluation batch processing orchestrator.

This module coordinates the evaluation-specific workflow:
1. Monitoring batch_job status for evaluations
2. Parsing evaluation results from batch output
3. Creating Langfuse dataset runs with traces
4. Updating evaluation_run with final status and scores
"""

import ast
import json
import logging
from collections import defaultdict
from typing import Any

from langfuse import Langfuse
from openai import OpenAI
from sqlmodel import Session, select

from app.core.batch.openai_provider import OpenAIBatchProvider
from app.core.util import configure_langfuse, configure_openai, now
from app.crud.batch_job import get_batch_job
from app.crud.batch_operations import download_batch_results
from app.crud.credentials import get_provider_credential
from app.crud.evaluation_batch import fetch_dataset_items
from app.crud.evaluation_langfuse import create_langfuse_dataset_run
from app.models import EvaluationRun

logger = logging.getLogger(__name__)


def parse_evaluation_output(
    raw_results: list[dict[str, Any]], dataset_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Parse batch output into evaluation results.

    This function extracts the generated output from the batch results
    and matches it with the ground truth from the dataset.

    Args:
        raw_results: Raw results from batch provider (list of JSONL lines)
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
    logger.info("Parsing evaluation results")

    # Create lookup map for dataset items by ID
    dataset_map = {item["id"]: item for item in dataset_items}

    results = []

    for line_num, response in enumerate(raw_results, 1):
        try:
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
                # Extract text from output (can be string, list, or complex structure)
                output = response_body.get("output", "")

                # If string, try to parse it (may be JSON or Python repr of list)
                if isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except (json.JSONDecodeError, ValueError):
                        try:
                            output = ast.literal_eval(output)
                        except (ValueError, SyntaxError):
                            # Keep as string if parsing fails
                            generated_output = output
                            output = None

                # If we have a list structure, extract text from message items
                if isinstance(output, list):
                    generated_output = ""
                    for item in output:
                        if isinstance(item, dict) and item.get("type") == "message":
                            for content in item.get("content", []):
                                if (
                                    isinstance(content, dict)
                                    and content.get("type") == "output_text"
                                ):
                                    generated_output = content.get("text", "")
                                    break
                            if generated_output:
                                break
                elif output is not None:
                    # output was not a string and not a list
                    generated_output = ""
                    logger.warning(
                        f"Item {item_id}: Unexpected output type: {type(output)}"
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

        except Exception as e:
            logger.error(f"Line {line_num}: Unexpected error: {e}")
            continue

    logger.info(
        f"Parsed {len(results)} evaluation results from {len(raw_results)} output lines"
    )
    return results


async def process_completed_evaluation(
    eval_run: EvaluationRun,
    session: Session,
    openai_client: OpenAI,
    langfuse: Langfuse,
) -> EvaluationRun:
    """
    Process a completed evaluation batch.

    This function:
    1. Downloads batch output from provider
    2. Parses results into question/output/ground_truth format
    3. Creates Langfuse dataset run with traces
    4. Updates evaluation_run with completion status

    Args:
        eval_run: EvaluationRun database object
        session: Database session
        openai_client: Configured OpenAI client
        langfuse: Configured Langfuse client

    Returns:
        Updated EvaluationRun object

    Raises:
        Exception: If processing fails
    """
    logger.info(f"Processing completed evaluation for run {eval_run.id}")

    try:
        # Step 1: Get batch_job
        if not eval_run.batch_job_id:
            raise ValueError(f"EvaluationRun {eval_run.id} has no batch_job_id")

        batch_job = get_batch_job(session=session, batch_job_id=eval_run.batch_job_id)
        if not batch_job:
            raise ValueError(
                f"BatchJob {eval_run.batch_job_id} not found for evaluation {eval_run.id}"
            )

        # Step 2: Create provider and download results
        logger.info(f"Step 1: Downloading batch results for batch_job {batch_job.id}")
        provider = OpenAIBatchProvider(client=openai_client)
        raw_results = download_batch_results(provider=provider, batch_job=batch_job)

        # Step 3: Fetch dataset items (needed for matching ground truth)
        logger.info(f"Step 2: Fetching dataset items for '{eval_run.dataset_name}'")
        dataset_items = fetch_dataset_items(
            langfuse=langfuse, dataset_name=eval_run.dataset_name
        )

        # Step 4: Parse evaluation results
        logger.info("Step 3: Parsing evaluation results")
        results = parse_evaluation_output(
            raw_results=raw_results, dataset_items=dataset_items
        )

        if not results:
            raise ValueError("No valid results found in batch output")

        # Step 5: Create Langfuse dataset run with traces
        logger.info("Step 4: Creating Langfuse dataset run with traces")
        create_langfuse_dataset_run(
            langfuse=langfuse,
            dataset_name=eval_run.dataset_name,
            run_name=eval_run.run_name,
            results=results,
        )

        # Step 6: Mark evaluation as completed
        logger.info("Step 5: Marking evaluation as completed")
        eval_run.status = "completed"
        eval_run.updated_at = now()

        # Copy S3 URL from batch_job if available
        if batch_job.raw_output_url:
            eval_run.s3_url = batch_job.raw_output_url

        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)

        logger.info(
            f"Successfully completed processing for evaluation run {eval_run.id}: "
            f"{len(results)} items processed"
        )

        return eval_run

    except Exception as e:
        logger.error(
            f"Failed to process completed evaluation for run {eval_run.id}: {e}",
            exc_info=True,
        )
        # Mark as failed
        eval_run.status = "failed"
        eval_run.error_message = f"Processing failed: {str(e)}"
        eval_run.updated_at = now()
        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)
        return eval_run


async def check_and_process_evaluation(
    eval_run: EvaluationRun,
    session: Session,
    openai_client: OpenAI,
    langfuse: Langfuse,
) -> dict[str, Any]:
    """
    Check evaluation batch status and process if completed.

    This function checks the batch_job status and triggers evaluation-specific
    processing when the batch is completed.

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
    logger.info(f"Checking evaluation run {eval_run.id}")

    previous_status = eval_run.status

    try:
        # Get batch_job
        if not eval_run.batch_job_id:
            raise ValueError(f"EvaluationRun {eval_run.id} has no batch_job_id")

        batch_job = get_batch_job(session=session, batch_job_id=eval_run.batch_job_id)
        if not batch_job:
            raise ValueError(
                f"BatchJob {eval_run.batch_job_id} not found for evaluation {eval_run.id}"
            )

        # IMPORTANT: Poll OpenAI to get the latest status before checking
        logger.info(f"Polling OpenAI for batch status: {batch_job.provider_batch_id}")
        provider = OpenAIBatchProvider(client=openai_client)
        from app.crud.batch_operations import poll_batch_status

        poll_batch_status(session=session, provider=provider, batch_job=batch_job)

        # Refresh batch_job to get the updated provider_status
        session.refresh(batch_job)
        provider_status = batch_job.provider_status

        # Handle different provider statuses
        if provider_status == "completed":
            # Process the completed evaluation
            logger.info(
                f"Batch {batch_job.provider_batch_id} completed, processing evaluation results..."
            )

            await process_completed_evaluation(
                eval_run=eval_run,
                session=session,
                openai_client=openai_client,
                langfuse=langfuse,
            )

            return {
                "run_id": eval_run.id,
                "run_name": eval_run.run_name,
                "previous_status": previous_status,
                "current_status": eval_run.status,
                "provider_status": provider_status,
                "action": "processed",
            }

        elif provider_status in ["failed", "expired", "cancelled"]:
            # Mark evaluation as failed based on provider status
            error_msg = batch_job.error_message or f"Provider batch {provider_status}"

            eval_run.status = "failed"
            eval_run.error_message = error_msg
            eval_run.updated_at = now()
            session.add(eval_run)
            session.commit()
            session.refresh(eval_run)

            logger.error(f"Batch {batch_job.provider_batch_id} failed: {error_msg}")

            return {
                "run_id": eval_run.id,
                "run_name": eval_run.run_name,
                "previous_status": previous_status,
                "current_status": "failed",
                "provider_status": provider_status,
                "action": "failed",
                "error": error_msg,
            }

        else:
            # Still in progress (validating, in_progress, finalizing)
            logger.info(
                f"Batch {batch_job.provider_batch_id} still processing (provider_status={provider_status})"
            )

            return {
                "run_id": eval_run.id,
                "run_name": eval_run.run_name,
                "previous_status": previous_status,
                "current_status": eval_run.status,
                "provider_status": provider_status,
                "action": "no_change",
            }

    except Exception as e:
        logger.error(f"Error checking evaluation run {eval_run.id}: {e}", exc_info=True)

        # Mark as failed
        eval_run.status = "failed"
        eval_run.error_message = f"Checking failed: {str(e)}"
        eval_run.updated_at = now()
        session.add(eval_run)
        session.commit()

        return {
            "run_id": eval_run.id,
            "run_name": eval_run.run_name,
            "previous_status": previous_status,
            "current_status": "failed",
            "provider_status": "unknown",
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

    # Get pending evaluations (status = "processing")
    statement = select(EvaluationRun).where(
        EvaluationRun.status == "processing",
        EvaluationRun.organization_id == org_id,
    )
    pending_runs = session.exec(statement).all()

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

    # Group evaluations by project_id since credentials are per project
    evaluations_by_project = defaultdict(list)
    for run in pending_runs:
        evaluations_by_project[run.project_id].append(run)

    # Process each project separately
    all_results = []
    total_processed_count = 0
    total_failed_count = 0
    total_still_processing_count = 0

    for project_id, project_runs in evaluations_by_project.items():
        logger.info(
            f"Processing {len(project_runs)} evaluations for project_id={project_id}"
        )

        try:
            # Get credentials for this project
            openai_credentials = get_provider_credential(
                session=session,
                org_id=org_id,
                project_id=project_id,
                provider="openai",
            )
            langfuse_credentials = get_provider_credential(
                session=session,
                org_id=org_id,
                project_id=project_id,
                provider="langfuse",
            )

            if not openai_credentials or not langfuse_credentials:
                logger.error(
                    f"Missing credentials for org_id={org_id}, project_id={project_id}: "
                    f"openai={bool(openai_credentials)}, langfuse={bool(langfuse_credentials)}"
                )
                # Mark all runs in this project as failed due to missing credentials
                for eval_run in project_runs:
                    all_results.append(
                        {
                            "run_id": eval_run.id,
                            "run_name": eval_run.run_name,
                            "action": "failed",
                            "error": "Missing OpenAI or Langfuse credentials",
                        }
                    )
                    total_failed_count += 1
                continue

            # Configure clients
            openai_client, openai_success = configure_openai(openai_credentials)
            langfuse, langfuse_success = configure_langfuse(langfuse_credentials)

            if not openai_success or not langfuse_success:
                logger.error(
                    f"Failed to configure clients for org_id={org_id}, project_id={project_id}"
                )
                # Mark all runs in this project as failed due to client configuration
                for eval_run in project_runs:
                    all_results.append(
                        {
                            "run_id": eval_run.id,
                            "run_name": eval_run.run_name,
                            "action": "failed",
                            "error": "Failed to configure API clients",
                        }
                    )
                    total_failed_count += 1
                continue

            # Process each evaluation in this project
            for eval_run in project_runs:
                try:
                    result = await check_and_process_evaluation(
                        eval_run=eval_run,
                        session=session,
                        openai_client=openai_client,
                        langfuse=langfuse,
                    )
                    all_results.append(result)

                    if result["action"] == "processed":
                        total_processed_count += 1
                    elif result["action"] == "failed":
                        total_failed_count += 1
                    else:
                        total_still_processing_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to check evaluation run {eval_run.id}: {e}",
                        exc_info=True,
                    )
                    all_results.append(
                        {
                            "run_id": eval_run.id,
                            "run_name": eval_run.run_name,
                            "action": "failed",
                            "error": str(e),
                        }
                    )
                    total_failed_count += 1

        except Exception as e:
            logger.error(f"Failed to process project {project_id}: {e}", exc_info=True)
            # Mark all runs in this project as failed
            for eval_run in project_runs:
                all_results.append(
                    {
                        "run_id": eval_run.id,
                        "run_name": eval_run.run_name,
                        "action": "failed",
                        "error": f"Project processing failed: {str(e)}",
                    }
                )
                total_failed_count += 1

    summary = {
        "total": len(pending_runs),
        "processed": total_processed_count,
        "failed": total_failed_count,
        "still_processing": total_still_processing_count,
        "details": all_results,
    }

    logger.info(
        f"Polling summary for org_id={org_id}: "
        f"{total_processed_count} processed, {total_failed_count} failed, "
        f"{total_still_processing_count} still processing"
    )

    return summary
