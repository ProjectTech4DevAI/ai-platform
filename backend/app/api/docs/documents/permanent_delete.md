This operation performs a soft delete on the document — the document remains in the database but is marked as deleted. However, the associated file in cloud storage is permanently deleted. This file deletion is irreversible.
If the document is part of an active collection, those collections
will be deleted using the collections delete interface. Noteably, this
means all OpenAI Vector Store's and Assistant's to which this document
belongs will be deleted.
