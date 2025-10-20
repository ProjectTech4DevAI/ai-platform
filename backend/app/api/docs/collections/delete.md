Remove a collection from the platform. This is a two step process:

1. Delete all OpenAI resources that were allocated: File's, the Vector
   Store, and the Assistant.
2. Delete the collection entry from the AI platform database.

No action is taken on the documents themselves: the contents of the
documents that were a part of the collection remain unchanged, those
documents can still be accessed via the documents endpoints. The response from this
endpoint will be a `collection_job` object which will contain the collection `job ID`,
status and action type ("DELETE"). when you take the id returned and use the collection job
info endpoint, if the job is successful, you will get the status as successful and nothing will
be returned for the collection as it has been deleted. Additionally, if a `callback_url` was
provided in the request body, you will receive a message indicating whether the deletion was
successful.
