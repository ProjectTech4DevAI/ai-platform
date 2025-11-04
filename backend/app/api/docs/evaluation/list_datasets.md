List all datasets for the current organization and project.

Returns a paginated list of dataset records ordered by most recent first.

## Query Parameters

- **limit**: Maximum number of datasets to return (default 50, max 100)
- **offset**: Number of datasets to skip for pagination (default 0)

## Returns

List of DatasetUploadResponse objects, each containing:
- dataset_id: Unique identifier for the dataset
- dataset_name: Name of the dataset (sanitized)
- total_items: Total number of items including duplication
- original_items: Number of original items before duplication
- duplication_factor: Factor by which items were duplicated
- langfuse_dataset_id: ID of the dataset in Langfuse
- object_store_url: URL to the CSV file in object storage
