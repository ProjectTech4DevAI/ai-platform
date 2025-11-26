Get the current status of a specific evaluation run.

Retrieves comprehensive information about an evaluation run including its current processing status, results (if completed), and error details (if failed).

## Path Parameters

- **evaluation_id**: ID of the evaluation run

## Query Parameters

- **get_trace_info** (optional, default: false): If true, fetch and include Langfuse trace scores with Q&A context. On first request, data is fetched from Langfuse and cached in the score column. Subsequent requests return cached data.

- **resync_score** (optional, default: false): If true, clear cached scores and re-fetch from Langfuse. Useful when new evaluators have been added or scores have been updated. Requires get_trace_info=true.

## Returns

EvaluationRunPublic with current status and results:
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
- created_at: Timestamp when the evaluation was created
- updated_at: Timestamp when the evaluation was last updated

## Usage

Use this endpoint to poll for evaluation progress. The evaluation is processed asynchronously by Celery Beat (every 60s), so you should poll periodically to check if the status has changed to "completed" or "failed".

## Error Responses

- **404**: Evaluation run not found or not accessible to this organization/project
