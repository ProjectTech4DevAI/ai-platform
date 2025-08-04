This endpoint initiates the fine-tuning of an OpenAI model using your custom dataset that you would have uploaded using the upload document endpoint. You can either specify a base model that you want to finetune, or leave it blank to use the default base model (currently "gpt-4.1-nano-2025-04-14" unless otherwise specified).

The split_ratio in the request body determines how your data is divided between training and testing. For example, a split ratio of 0.5 means 50% of your data will be used for training, and the remaining 50% for testing. You can also provide multiple split ratios—for instance, [0.7, 0.9]. This will trigger multiple fine-tuning jobs, one for each ratio, effectively training multiple models on different portions of your dataset.

The system handles the fine-tuning process by interacting with OpenAI's APIs under the hood. These include:

- [Openai File create to upload your training and testing files](https://platform.openai.com/docs/api-reference/files/create)

- [Openai Fine Tuning Job create to initiate each fine-tuning job](https://platform.openai.com/docs/api-reference/fine_tuning/create)

If successful, the response will include a message along with a list of fine-tuning jobs that were initiated. Each job object includes:

- id: the internal ID of the fine-tuning job
- document_id: the ID of the document used for fine-tuning
- split_ratio: the data split used for that job
- status: the initial status of the job (usually "pending")
