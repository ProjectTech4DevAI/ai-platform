Upload a CSV file containing Golden Q&A pairs.

This endpoint:
1. Sanitizes the dataset name (removes spaces, special characters)
2. Validates and parses the CSV file
3. Uploads CSV to object store (if credentials configured)
4. Uploads dataset to Langfuse (for immediate use)
5. Stores metadata in database

## Dataset Name

- Will be sanitized for Langfuse compatibility
- Spaces replaced with underscores
- Special characters removed
- Converted to lowercase
- Example: "My Dataset 01!" becomes "my_dataset_01"

## CSV Format

- Must contain 'question' and 'answer' columns
- Can have additional columns (will be ignored)
- Missing values in 'question' or 'answer' rows will be skipped

## Duplication Factor

- Minimum: 1 (no duplication)
- Maximum: 5
- Default: 5
- Each item in the dataset will be duplicated this many times
- Used to ensure statistical significance in evaluation results

## Example CSV

```
question,answer
"What is the capital of France?","Paris"
"What is 2+2?","4"
```

## Returns

DatasetUploadResponse with dataset_id, object_store_url, and Langfuse details (dataset_name in response will be the sanitized version)
