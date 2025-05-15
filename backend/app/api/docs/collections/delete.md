Remove a collection from the platform. This is a two step process:

1. Delete all OpenAI resources that were allocated: File's, the Vector
   Store, and the Assistant.
2. Delete the collection entry from the AI platform database.

No action is taken on the documents themselves: the contents of the
documents that were a part of the collection remain unchanged, those
documents can still be accessed via the documents endpoints.
