Retrieve detailed information about `a specific collection by its ID` from the collection table. This endpoint returns the collection object including its project, organization,
timestamps, and associated LLM service details (`llm_service_id`).

Additionally, if the `include_docs` flag in the request body is true then you will get a list of document IDs associated with a given collection as well. Documents returned are not only stored by the AI platform, but also by OpenAI.
