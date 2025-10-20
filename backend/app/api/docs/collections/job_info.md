Retrieve information about a collection job by the collection job ID. This endpoint provides detailed status and metadata for a specific collection job in the AI platform. It is especially useful for:

* Fetching the collection job object containing the ID which will be collection job id, collection ID, status of the job as well as error message.

* If the job has finished, has been successful and it was a job of creation of collection then this endpoint will fetch the associated collection details from the collection table, including:
    - `llm_service_id`: The OpenAI assistant or model used for the collection.
    - Collection metadata such as ID, project, organization, and timestamps.

* If the job of delete collection was successful, we will get the status as successful and nothing will be returned as collection.

* Containing a simplified error messages in the retrieved collection job object when a job has failed.
