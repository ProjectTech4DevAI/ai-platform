Retrieve detailed information about a specific collection by its ID from the collection table. Note that this endpoint CANNOT be used as a polling endpoint for collection creation because an entry will be made in the collection table only after the resource creation and association has been successful.

This endpoint returns metadata for the collection, including its project, organization,
timestamps, and associated LLM service details (`llm_service_id`).

Additionally, if the "include_docs" flag in the request body is true then you will get a list of document IDs associated with a given collection as well. Documents returned are not only stored by the AI platform, but also by OpenAI.
