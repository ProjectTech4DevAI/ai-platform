List all evaluation runs for the current organization and project.

Returns a paginated list of evaluation runs ordered by most recent first. Each evaluation run represents a batch processing job evaluating a dataset against a specific configuration.

## Query Parameters

- **limit**: Maximum number of runs to return (default 50)
- **offset**: Number of runs to skip (for pagination, default 0)

## Returns

List of EvaluationRunPublic objects, each containing:
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
