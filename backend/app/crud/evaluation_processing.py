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
from app.crud.batch_operations import (
    download_batch_results,
    upload_batch_results_to_object_store,
)
from app.crud.credentials import get_provider_credential
from app.crud.evaluation_batch import fetch_dataset_items
from app.crud.evaluation_embeddings import (
    calculate_average_similarity,
    parse_embedding_results,
    start_embedding_batch,
)
from app.crud.evaluation_langfuse import (
    create_langfuse_dataset_run,
    update_traces_with_cosine_scores,
)
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
    4. Starts embedding batch for similarity scoring (keeps status as "processing")

    Args:
        eval_run: EvaluationRun database object
        session: Database session
        openai_client: Configured OpenAI client
        langfuse: Configured Langfuse client

    Returns:
        Updated EvaluationRun object (with embedding_batch_job_id set)

    Raises:
        Exception: If processing fails
    """
    log_prefix = f"[org={eval_run.organization_id}][project={eval_run.project_id}][eval={eval_run.id}]"
    logger.info(f"{log_prefix} Processing completed evaluation")

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
        logger.info(
            f"{log_prefix} Downloading batch results for batch_job {batch_job.id}"
        )
        provider = OpenAIBatchProvider(client=openai_client)
        raw_results = download_batch_results(provider=provider, batch_job=batch_job)

        # Step 2a: Upload raw results to object store for evaluation_run
        object_store_url = None
        try:
            object_store_url = upload_batch_results_to_object_store(
                session=session, batch_job=batch_job, results=raw_results
            )
        except Exception as store_error:
            logger.warning(f"{log_prefix} Object store upload failed: {store_error}")

        # Step 3: Fetch dataset items (needed for matching ground truth)
        logger.info(
            f"{log_prefix} Fetching dataset items for '{eval_run.dataset_name}'"
        )
        dataset_items = fetch_dataset_items(
            langfuse=langfuse, dataset_name=eval_run.dataset_name
        )

        # Step 4: Parse evaluation results
        results = parse_evaluation_output(
            raw_results=raw_results, dataset_items=dataset_items
        )

        if not results:
            raise ValueError("No valid results found in batch output")

        # Step 5: Create Langfuse dataset run with traces
        trace_id_mapping = create_langfuse_dataset_run(
            langfuse=langfuse,
            dataset_name=eval_run.dataset_name,
            run_name=eval_run.run_name,
            results=results,
        )

        # Store object store URL in database
        if object_store_url:
            eval_run.object_store_url = object_store_url
            session.add(eval_run)
            session.commit()

        # Step 6: Start embedding batch for similarity scoring
        # Pass trace_id_mapping directly without storing in DB
        try:
            eval_run = start_embedding_batch(
                session=session,
                openai_client=openai_client,
                eval_run=eval_run,
                results=results,
                trace_id_mapping=trace_id_mapping,
            )
            # Note: Status remains "processing" until embeddings complete

        except Exception as e:
            logger.error(
                f"{log_prefix} Failed to start embedding batch: {e}",
                exc_info=True,
            )
            # Don't fail the entire evaluation, just mark as completed without embeddings
            eval_run.status = "completed"
            eval_run.error_message = f"Embeddings failed: {str(e)}"
            eval_run.updated_at = now()
            session.add(eval_run)
            session.commit()
            session.refresh(eval_run)

        logger.info(f"{log_prefix} Processed evaluation: {len(results)} items")

        return eval_run

    except Exception as e:
        logger.error(
            f"{log_prefix} Failed to process completed evaluation: {e}",
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


async def process_completed_embedding_batch(
    eval_run: EvaluationRun,
    session: Session,
    openai_client: OpenAI,
    langfuse: Langfuse,
) -> EvaluationRun:
    """
    Process a completed embedding batch and calculate similarity scores.

    This function:
    1. Downloads embedding batch results
    2. Parses embeddings (output + ground_truth pairs)
    3. Calculates cosine similarity for each pair
    4. Calculates average and statistics
    5. Updates eval_run.score with results
    6. Updates Langfuse traces with per-item cosine similarity scores
    7. Marks evaluation as completed

    Args:
        eval_run: EvaluationRun database object
        session: Database session
        openai_client: Configured OpenAI client
        langfuse: Configured Langfuse client

    Returns:
        Updated EvaluationRun object with similarity scores

    Raises:
        Exception: If processing fails
    """
    log_prefix = f"[org={eval_run.organization_id}][project={eval_run.project_id}][eval={eval_run.id}]"
    logger.info(f"{log_prefix} Processing completed embedding batch")

    try:
        # Step 1: Get embedding_batch_job
        if not eval_run.embedding_batch_job_id:
            raise ValueError(
                f"EvaluationRun {eval_run.id} has no embedding_batch_job_id"
            )

        embedding_batch_job = get_batch_job(
            session=session, batch_job_id=eval_run.embedding_batch_job_id
        )
        if not embedding_batch_job:
            raise ValueError(
                f"Embedding BatchJob {eval_run.embedding_batch_job_id} not found for evaluation {eval_run.id}"
            )

        # Step 2: Create provider and download results
        provider = OpenAIBatchProvider(client=openai_client)
        raw_results = download_batch_results(
            provider=provider, batch_job=embedding_batch_job
        )

        # Step 3: Parse embedding results
        embedding_pairs = parse_embedding_results(raw_results=raw_results)

        if not embedding_pairs:
            raise ValueError("No valid embedding pairs found in batch output")

        # Step 4: Calculate similarity scores
        similarity_stats = calculate_average_similarity(embedding_pairs=embedding_pairs)

        # Step 5: Update evaluation_run with scores
        if eval_run.score is None:
            eval_run.score = {}

        eval_run.score["cosine_similarity"] = {
            "avg": similarity_stats["cosine_similarity_avg"],
            "min": similarity_stats["cosine_similarity_min"],
            "max": similarity_stats["cosine_similarity_max"],
            "std": similarity_stats["cosine_similarity_std"],
            "total_pairs": similarity_stats["total_pairs"],
        }

        # Optionally store per-item scores if not too large
        if len(similarity_stats.get("per_item_scores", [])) <= 100:
            eval_run.score["cosine_similarity"]["per_item_scores"] = similarity_stats[
                "per_item_scores"
            ]

        # Step 6: Update Langfuse traces with cosine similarity scores
        logger.info(
            f"{log_prefix} Updating Langfuse traces with cosine similarity scores"
        )
        per_item_scores = similarity_stats.get("per_item_scores", [])
        if per_item_scores:
            try:
                update_traces_with_cosine_scores(
                    langfuse=langfuse,
                    per_item_scores=per_item_scores,
                )
            except Exception as e:
                # Log error but don't fail the evaluation
                logger.error(
                    f"{log_prefix} Failed to update Langfuse traces with scores: {e}",
                    exc_info=True,
                )

        # Step 7: Mark evaluation as completed
        eval_run.status = "completed"
        eval_run.updated_at = now()

        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)

        logger.info(
            f"{log_prefix} Completed evaluation: "
            f"avg_similarity={similarity_stats['cosine_similarity_avg']:.3f}"
        )

        return eval_run

    except Exception as e:
        logger.error(
            f"{log_prefix} Failed to process completed embedding batch: {e}",
            exc_info=True,
        )
        # Mark as completed anyway, but with error message
        eval_run.status = "completed"
        eval_run.error_message = f"Embedding processing failed: {str(e)}"
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

    This function handles both the response batch and embedding batch:
    1. If embedding_batch_job_id exists, checks and processes embedding batch first
    2. Otherwise, checks and processes the main response batch
    3. Triggers appropriate processing based on batch completion status

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
            "action": "processed" | "embeddings_completed" | "embeddings_failed" | "failed" | "no_change"
        }
    """
    log_prefix = f"[org={eval_run.organization_id}][project={eval_run.project_id}][eval={eval_run.id}]"
    previous_status = eval_run.status

    try:
        # Check if we need to process embedding batch first
        if eval_run.embedding_batch_job_id and eval_run.status == "processing":
            embedding_batch_job = get_batch_job(
                session=session, batch_job_id=eval_run.embedding_batch_job_id
            )

            if embedding_batch_job:
                # Poll embedding batch status
                provider = OpenAIBatchProvider(client=openai_client)
                from app.crud.batch_operations import poll_batch_status

                poll_batch_status(
                    session=session, provider=provider, batch_job=embedding_batch_job
                )
                session.refresh(embedding_batch_job)

                embedding_status = embedding_batch_job.provider_status

                if embedding_status == "completed":
                    logger.info(
                        f"{log_prefix} Processing embedding batch {embedding_batch_job.provider_batch_id}"
                    )

                    await process_completed_embedding_batch(
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
                        "provider_status": embedding_status,
                        "action": "embeddings_completed",
                    }

                elif embedding_status in ["failed", "expired", "cancelled"]:
                    logger.error(
                        f"{log_prefix} Embedding batch {embedding_batch_job.provider_batch_id} failed: "
                        f"{embedding_batch_job.error_message}"
                    )
                    # Mark as completed without embeddings
                    eval_run.status = "completed"
                    eval_run.error_message = (
                        f"Embedding batch failed: {embedding_batch_job.error_message}"
                    )
                    eval_run.updated_at = now()
                    session.add(eval_run)
                    session.commit()
                    session.refresh(eval_run)

                    return {
                        "run_id": eval_run.id,
                        "run_name": eval_run.run_name,
                        "previous_status": previous_status,
                        "current_status": "completed",
                        "provider_status": embedding_status,
                        "action": "embeddings_failed",
                    }

                else:
                    # Embedding batch still processing
                    return {
                        "run_id": eval_run.id,
                        "run_name": eval_run.run_name,
                        "previous_status": previous_status,
                        "current_status": eval_run.status,
                        "provider_status": embedding_status,
                        "action": "no_change",
                    }

        # Get batch_job (main response batch)
        if not eval_run.batch_job_id:
            raise ValueError(f"EvaluationRun {eval_run.id} has no batch_job_id")

        batch_job = get_batch_job(session=session, batch_job_id=eval_run.batch_job_id)
        if not batch_job:
            raise ValueError(
                f"BatchJob {eval_run.batch_job_id} not found for evaluation {eval_run.id}"
            )

        # IMPORTANT: Poll OpenAI to get the latest status before checking
        provider = OpenAIBatchProvider(client=openai_client)
        from app.crud.batch_operations import poll_batch_status

        poll_batch_status(session=session, provider=provider, batch_job=batch_job)

        # Refresh batch_job to get the updated provider_status
        session.refresh(batch_job)
        provider_status = batch_job.provider_status

        # Handle different provider statuses
        if provider_status == "completed":
            # Process the completed evaluation
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

            logger.error(
                f"{log_prefix} Batch {batch_job.provider_batch_id} failed: {error_msg}"
            )

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
            return {
                "run_id": eval_run.id,
                "run_name": eval_run.run_name,
                "previous_status": previous_status,
                "current_status": eval_run.status,
                "provider_status": provider_status,
                "action": "no_change",
            }

    except Exception as e:
        logger.error(f"{log_prefix} Error checking evaluation: {e}", exc_info=True)

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
    # Get pending evaluations (status = "processing")
    statement = select(EvaluationRun).where(
        EvaluationRun.status == "processing",
        EvaluationRun.organization_id == org_id,
    )
    pending_runs = session.exec(statement).all()

    if not pending_runs:
        return {
            "total": 0,
            "processed": 0,
            "failed": 0,
            "still_processing": 0,
            "details": [],
        }
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
