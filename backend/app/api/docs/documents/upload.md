Upload a document to the AI platform.

- If only a file is provided, the document will be uploaded and stored, and its ID will be returned.
- If a target format is specified, a transformation job will also be created to transform document into target format in the background. The response will include both the uploaded document details and information about the transformation job.

### Supported Transformations

The following (source_format → target_format) transformations are supported:

- pdf → markdown
  - zerox 

### Transformers

Available transformer names and their implementations, default transformer is zerox:

- `zerox`