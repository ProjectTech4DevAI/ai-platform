Start an evaluation using OpenAI Batch API.

This endpoint:
1. Fetches the dataset from database and validates it has Langfuse dataset ID
2. Creates an EvaluationRun record in the database
3. Fetches dataset items from Langfuse
4. Builds JSONL for batch processing (config is used as-is)
5. Creates a batch job via the generic batch infrastructure
6. Returns the evaluation run details with batch_job_id

The batch will be processed asynchronously by Celery Beat (every 60s).
Use GET /evaluations/{evaluation_id} to check progress.

## Request Body

- **dataset_id** (required): ID of the evaluation dataset (from /evaluations/datasets)
- **experiment_name** (required): Name for this evaluation experiment/run
- **config** (optional): Configuration dict that will be used as-is in JSONL generation. Can include any OpenAI Responses API parameters like:
  - model: str (e.g., "gpt-4o", "gpt-5")
  - instructions: str
  - tools: list (e.g., [{"type": "file_search", "vector_store_ids": [...]}])
  - reasoning: dict (e.g., {"effort": "low"})
  - text: dict (e.g., {"verbosity": "low"})
  - temperature: float
  - include: list (e.g., ["file_search_call.results"])
  - Note: "input" will be added automatically from the dataset
- **assistant_id** (optional): Assistant ID to fetch configuration from. If provided, configuration will be fetched from the assistant in the database. Config can be passed as empty dict {} when using assistant_id.

## Example with config

```json
{
    "dataset_id": 123,
    "experiment_name": "test_run",
    "config": {
        "model": "gpt-4.1",
        "instructions": "You are a helpful FAQ assistant.",
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": ["vs_12345"],
                "max_num_results": 3
            }
        ],
        "include": ["file_search_call.results"]
    }
}
```

## Example with assistant_id

```json
{
    "dataset_id": 123,
    "experiment_name": "test_run",
    "config": {},
    "assistant_id": "asst_xyz"
}
```

## Returns

EvaluationRunPublic with batch details and status:
- id: Evaluation run ID
- run_name: Name of the evaluation run
- dataset_name: Name of the dataset used
- dataset_id: ID of the dataset used
- config: Configuration used for the evaluation
- batch_job_id: ID of the batch job processing this evaluation
- status: Current status (pending, running, completed, failed)
- total_items: Total number of items being evaluated
- completed_items: Number of items completed so far
- results: Evaluation results (when completed)
- error_message: Error message if failed

## Error Responses

- **404**: Dataset or assistant not found or not accessible
- **400**: Missing required credentials (OpenAI or Langfuse), dataset missing Langfuse ID, or config missing required fields
- **500**: Failed to configure API clients or start batch evaluation
