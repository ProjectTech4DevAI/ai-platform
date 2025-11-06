Delete a dataset by ID.

This will remove the dataset record from the database. The CSV file in object store (if exists) will remain for audit purposes, but the dataset will no longer be accessible for creating new evaluations.

## Path Parameters

- **dataset_id**: ID of the dataset to delete

## Returns

Success message with deleted dataset details:
- message: Confirmation message
- dataset_id: ID of the deleted dataset

## Error Responses

- **404**: Dataset not found or not accessible to your organization/project
- **400**: Dataset cannot be deleted (e.g., has active evaluation runs)
