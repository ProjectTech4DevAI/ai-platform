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
) -> None:
    """
    Create a dataset run in Langfuse with traces for each evaluation item.

    This function:
    1. Gets the dataset from Langfuse (which already exists)
    2. For each result, creates a trace linked to the dataset item
    3. Logs input (question), output (generated_output), and expected (ground_truth)

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
        logger.info(f"Found dataset '{dataset_name}' with {len(dataset.items)} items")

        # Create a map of item IDs for quick lookup
        dataset_items_map = {item.id: item for item in dataset.items}

        created_traces = 0
        skipped_items = 0

        # Create a trace for each result
        for idx, result in enumerate(results, 1):
            item_id = result["item_id"]
            question = result["question"]
            generated_output = result["generated_output"]
            ground_truth = result["ground_truth"]

            # Get the dataset item
            dataset_item = dataset_items_map.get(item_id)
            if not dataset_item:
                logger.warning(
                    f"Item {idx}/{len(results)}: Dataset item '{item_id}' not found, skipping"
                )
                skipped_items += 1
                continue

            try:
                # Use item.observe to create a trace linked to the dataset item
                with dataset_item.observe(run_name=run_name) as trace_id:
                    # Update the trace with input and output
                    langfuse.trace(
                        id=trace_id,
                        input={"question": question},
                        output={"answer": generated_output},
                        metadata={
                            "ground_truth": ground_truth,
                            "item_id": item_id,
                        },
                    )
                    created_traces += 1

                if idx % 10 == 0:
                    logger.info(
                        f"Progress: Created {idx}/{len(results)} traces for run '{run_name}'"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to create trace for item {item_id}: {e}", exc_info=True
                )
                skipped_items += 1
                continue

        # Flush to ensure all traces are sent
        langfuse.flush()

        logger.info(
            f"Successfully created Langfuse dataset run '{run_name}': "
            f"{created_traces} traces created, {skipped_items} items skipped"
        )

    except Exception as e:
        logger.error(
            f"Failed to create Langfuse dataset run '{run_name}': {e}", exc_info=True
        )
        raise
