Retrieve detailed information about a specific collection by its ID from the collection table. Note that this endpoint CANNOT be used as a polling endpoint for collection creation because an entry will be made in the collection table only after the resource creation and association has been successful.

This endpoint returns metadata for the collection, including its project, organization,
timestamps, and associated LLM service details (`llm_service_id`).
