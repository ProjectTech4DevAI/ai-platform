Get details of a specific dataset by ID.

Retrieves comprehensive information about a dataset including metadata, object store URL, and Langfuse integration details.

## Path Parameters

- **dataset_id**: ID of the dataset to retrieve

## Returns

DatasetUploadResponse with dataset details:
- dataset_id: Unique identifier for the dataset
- dataset_name: Name of the dataset (sanitized)
- total_items: Total number of items including duplication
- original_items: Number of original items before duplication
- duplication_factor: Factor by which items were duplicated
- langfuse_dataset_id: ID of the dataset in Langfuse
- object_store_url: URL to the CSV file in object storage

## Error Responses

- **404**: Dataset not found or not accessible to your organization/project
