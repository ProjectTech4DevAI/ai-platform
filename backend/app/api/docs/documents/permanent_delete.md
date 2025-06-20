This operation soft deletes the document — meaning its metadata and reference are retained in the database, but it is marked as deleted. The actual file stored in cloud storage (e.g., S3) is permanently deleted, and this action is irreversible.
If the document is part of an active collection, those collections
will be deleted using the collections delete interface. Noteably, this
means all OpenAI Vector Store's and Assistant's to which this document
belongs will be deleted.
