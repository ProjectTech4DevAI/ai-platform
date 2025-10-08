Setup and configure the document store that is pertinent to the RAG
pipeline:

* Make OpenAI
  [File](https://platform.openai.com/docs/api-reference/files)'s from
  documents stored in the cloud (see the `documents` interface).
* Create an OpenAI [Vector
  Store](https://platform.openai.com/docs/api-reference/vector-stores)
  based on those File's.
* Attach the Vector Store to an OpenAI
  [Assistant](https://platform.openai.com/docs/api-reference/assistants). Use
  parameters in the request body relevant to an Assistant to flesh out
  its configuration.

If any one of the OpenAI interactions fail, all OpenAI resources are
cleaned up. If a Vector Store is unable to be created, for example,
all File's that were uploaded to OpenAI are removed from
OpenAI. Failure can occur from OpenAI being down, or some parameter
value being invalid. It can also fail due to document types not be
accepted. This is especially true for PDFs that may not be parseable.

The immediate response from the endpoint is `collection_job` object which is
going to contain the collection "job ID", status and action type ("CREATE").
Once the collection has been created, information about the collection will
be returned to the user via the callback URL. If a callback URL is not provided,
clients can poll the `collection job info` endpoint with the `id` in the
`collection_job` object returned as it is the `job id`, to retrieve the same information.
