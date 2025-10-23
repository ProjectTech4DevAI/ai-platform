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
                         "ground_truth": "4"
                     },
                     ...
                 ]

    Returns:
        dict[str, str]: Mapping of item_id to Langfuse trace_id

    Raises:
        Exception: If Langfuse operations fail
    """
    logger.info(
        f"Creating Langfuse dataset run '{run_name}' for dataset '{dataset_name}' "
        f"with {len(results)} items"
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

            dataset_item = dataset_items_map.get(item_id)
            if not dataset_item:
                logger.warning(f"Dataset item '{item_id}' not found, skipping")
                continue

            try:
                with dataset_item.observe(run_name=run_name) as trace_id:
                    langfuse.trace(
                        id=trace_id,
                        input={"question": question},
                        output={"answer": generated_output},
                        metadata={
                            "ground_truth": ground_truth,
                            "item_id": item_id,
                        },
                    )
                    trace_id_mapping[item_id] = trace_id

            except Exception as e:
                logger.error(
                    f"Failed to create trace for item {item_id}: {e}", exc_info=True
                )
                continue

        langfuse.flush()
        logger.info(
            f"Created Langfuse dataset run '{run_name}' with {len(trace_id_mapping)} traces"
        )

        return trace_id_mapping

    except Exception as e:
        logger.error(
            f"Failed to create Langfuse dataset run '{run_name}': {e}", exc_info=True
        )
        raise


def update_traces_with_cosine_scores(
    langfuse: Langfuse,
    trace_id_mapping: dict[str, str],
    per_item_scores: list[dict[str, Any]],
) -> None:
    """
    Update Langfuse traces with cosine similarity scores.

    This function adds custom "cosine_similarity" scores to traces at the trace level,
    allowing them to be visualized in the Langfuse UI.

    Args:
        langfuse: Configured Langfuse client
        trace_id_mapping: Mapping of item_id to Langfuse trace_id
        per_item_scores: List of per-item score dictionaries from calculate_average_similarity()
                        Format: [
                            {
                                "item_id": "item_123",
                                "cosine_similarity": 0.95
                            },
                            ...
                        ]

    Note:
        This function logs errors but does not raise exceptions to avoid blocking
        evaluation completion if Langfuse updates fail.
    """
    for score_item in per_item_scores:
        item_id = score_item.get("item_id")
        cosine_score = score_item.get("cosine_similarity")
        trace_id = trace_id_mapping.get(item_id)

        if not trace_id:
            continue

        try:
            langfuse.score(
                trace_id=trace_id,
                name="cosine_similarity",
                value=cosine_score,
                comment="Cosine similarity between generated output and ground truth embeddings",
            )
        except Exception as e:
            logger.error(
                f"Failed to add score for trace {trace_id} (item {item_id}): {e}",
                exc_info=True,
            )

    langfuse.flush()
