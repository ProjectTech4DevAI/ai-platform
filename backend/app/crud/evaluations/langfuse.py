"""
Langfuse integration for evaluation runs.

This module handles:
1. Creating dataset runs in Langfuse
2. Creating traces for each evaluation item
3. Uploading results to Langfuse for visualization
"""

import logging
from typing import Any

from langfuse import Langfuse

logger = logging.getLogger(__name__)


def create_langfuse_dataset_run(
    langfuse: Langfuse,
    dataset_name: str,
    run_name: str,
    results: list[dict[str, Any]],
) -> dict[str, str]:
    """
    Create a dataset run in Langfuse with traces for each evaluation item.

    This function:
    1. Gets the dataset from Langfuse (which already exists)
    2. For each result, creates a trace linked to the dataset item
    3. Logs input (question), output (generated_output), and expected (ground_truth)
    4. Returns a mapping of item_id -> trace_id for later score updates

    Args:
        langfuse: Configured Langfuse client
        dataset_name: Name of the dataset in Langfuse
        run_name: Name for this evaluation run
        results: List of evaluation results from parse_batch_output()
                 Format: [
                     {
                         "item_id": "item_123",
                         "question": "What is 2+2?",
                         "generated_output": "4",
                         "ground_truth": "4",
                         "response_id": "resp_0b99aadfead1fb62006908e7f540c48197bd110183a347c1d8"
                     },
                     ...
                 ]

    Returns:
        dict[str, str]: Mapping of item_id to Langfuse trace_id

    Raises:
        Exception: If Langfuse operations fail
    """
    logger.info(
        f"[create_langfuse_dataset_run] Creating Langfuse dataset run | "
        f"run_name={run_name} | dataset={dataset_name} | items={len(results)}"
    )

    try:
        # Get the dataset
        dataset = langfuse.get_dataset(dataset_name)
        dataset_items_map = {item.id: item for item in dataset.items}

        trace_id_mapping = {}

        # Create a trace for each result
        for result in results:
            item_id = result["item_id"]
            question = result["question"]
            generated_output = result["generated_output"]
            ground_truth = result["ground_truth"]
            response_id = result.get("response_id")

            dataset_item = dataset_items_map.get(item_id)
            if not dataset_item:
                logger.warning(
                    f"[create_langfuse_dataset_run] Dataset item not found, skipping | "
                    f"item_id={item_id}"
                )
                continue

            try:
                with dataset_item.observe(run_name=run_name) as trace_id:
                    metadata = {
                        "ground_truth": ground_truth,
                        "item_id": item_id,
                    }
                    if response_id:
                        metadata["response_id"] = response_id

                    langfuse.trace(
                        id=trace_id,
                        input={"question": question},
                        output={"answer": generated_output},
                        metadata=metadata,
                    )
                    trace_id_mapping[item_id] = trace_id

            except Exception as e:
                logger.error(
                    f"[create_langfuse_dataset_run] Failed to create trace | "
                    f"item_id={item_id} | {e}",
                    exc_info=True,
                )
                continue

        langfuse.flush()
        logger.info(
            f"[create_langfuse_dataset_run] Created Langfuse dataset run | "
            f"run_name={run_name} | traces={len(trace_id_mapping)}"
        )

        return trace_id_mapping

    except Exception as e:
        logger.error(
            f"[create_langfuse_dataset_run] Failed to create Langfuse dataset run | "
            f"run_name={run_name} | {e}",
            exc_info=True,
        )
        raise


def update_traces_with_cosine_scores(
    langfuse: Langfuse,
    per_item_scores: list[dict[str, Any]],
) -> None:
    """
    Update Langfuse traces with cosine similarity scores.

    This function adds custom "cosine_similarity" scores to traces at the trace level,
    allowing them to be visualized in the Langfuse UI.

    Args:
        langfuse: Configured Langfuse client
        per_item_scores: List of per-item score dictionaries from
            calculate_average_similarity()
                        Format: [
                            {
                                "trace_id": "trace-uuid-123",
                                "cosine_similarity": 0.95
                            },
                            ...
                        ]

    Note:
        This function logs errors but does not raise exceptions to avoid blocking
        evaluation completion if Langfuse updates fail.
    """
    for score_item in per_item_scores:
        trace_id = score_item.get("trace_id")
        cosine_score = score_item.get("cosine_similarity")

        if not trace_id:
            logger.warning(
                "[update_traces_with_cosine_scores] Score item missing trace_id, skipping"
            )
            continue

        try:
            langfuse.score(
                trace_id=trace_id,
                name="cosine_similarity",
                value=cosine_score,
                comment=(
                    "Cosine similarity between generated output and "
                    "ground truth embeddings"
                ),
            )
        except Exception as e:
            logger.error(
                f"[update_traces_with_cosine_scores] Failed to add score | "
                f"trace_id={trace_id} | {e}",
                exc_info=True,
            )

    langfuse.flush()


def upload_dataset_to_langfuse_from_csv(
    langfuse: Langfuse,
    csv_content: bytes,
    dataset_name: str,
    duplication_factor: int,
) -> tuple[str, int]:
    """
    Upload a dataset to Langfuse from CSV content.

    This function parses CSV content and uploads it to Langfuse with duplication.
    Used when re-uploading datasets from S3 storage.

    Args:
        langfuse: Configured Langfuse client
        csv_content: Raw CSV content as bytes
        dataset_name: Name for the dataset in Langfuse
        duplication_factor: Number of times to duplicate each item

    Returns:
        Tuple of (langfuse_dataset_id, total_items_uploaded)

    Raises:
        ValueError: If CSV is invalid or empty
        Exception: If Langfuse operations fail
    """
    import csv
    import io

    logger.info(
        f"[upload_dataset_to_langfuse_from_csv] Uploading dataset to Langfuse from CSV | "
        f"dataset={dataset_name} | duplication_factor={duplication_factor}"
    )

    try:
        # Parse CSV content
        csv_text = csv_content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        csv_reader.fieldnames = [name.strip() for name in csv_reader.fieldnames]

        # Validate CSV headers
        if (
            "question" not in csv_reader.fieldnames
            or "answer" not in csv_reader.fieldnames
        ):
            raise ValueError(
                f"CSV must contain 'question' and 'answer' columns. "
                f"Found columns: {csv_reader.fieldnames}"
            )

        # Read all rows from CSV
        original_items = []
        for row in csv_reader:
            question = row.get("question", "").strip()
            answer = row.get("answer", "").strip()

            if not question or not answer:
                logger.warning(
                    f"[upload_dataset_to_langfuse_from_csv] Skipping row with empty question or answer | {row}"
                )
                continue

            original_items.append({"question": question, "answer": answer})

        if not original_items:
            raise ValueError("No valid items found in CSV file")

        logger.info(
            f"[upload_dataset_to_langfuse_from_csv] Parsed items from CSV | "
            f"original={len(original_items)} | duplication_factor={duplication_factor} | "
            f"total={len(original_items) * duplication_factor}"
        )

        # Create or get dataset in Langfuse
        dataset = langfuse.create_dataset(name=dataset_name)

        # Upload items with duplication
        total_uploaded = 0
        for item in original_items:
            # Duplicate each item N times
            for duplicate_num in range(duplication_factor):
                try:
                    langfuse.create_dataset_item(
                        dataset_name=dataset_name,
                        input={"question": item["question"]},
                        expected_output={"answer": item["answer"]},
                        metadata={
                            "original_question": item["question"],
                            "duplicate_number": duplicate_num + 1,
                            "duplication_factor": duplication_factor,
                        },
                    )
                    total_uploaded += 1
                except Exception as e:
                    logger.error(
                        f"[upload_dataset_to_langfuse_from_csv] Failed to upload item | "
                        f"duplicate={duplicate_num + 1} | question={item['question'][:50]}... | {e}"
                    )

        # Flush to ensure all items are uploaded
        langfuse.flush()

        langfuse_dataset_id = dataset.id if hasattr(dataset, "id") else None

        logger.info(
            f"[upload_dataset_to_langfuse_from_csv] Successfully uploaded items to Langfuse dataset | "
            f"items={total_uploaded} | dataset={dataset_name} | id={langfuse_dataset_id}"
        )

        return langfuse_dataset_id, total_uploaded

    except Exception as e:
        logger.error(
            f"[upload_dataset_to_langfuse_from_csv] Failed to upload dataset to Langfuse | "
            f"dataset={dataset_name} | {e}",
            exc_info=True,
        )
        raise
