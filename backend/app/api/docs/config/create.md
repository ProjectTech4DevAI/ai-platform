Create a new LLM configuration with an initial version.

Configurations allow you to store and manage reusable LLM parameters
(such as temperature, max_tokens, model selection, etc.) with version control.

**Key Features:**
* Automatically creates an initial version (v1) with the provided configuration
* Enforces unique configuration names per project
* Stores provider-specific parameters as flexible JSON (config_blob)
* Supports optional commit messages for tracking changes
* Provider-agnostic storage - params are passed through to the provider as-is

**Request Field Details:**

- `name` (required): Unique configuration name
- `description` (optional): Human-readable description for the config
- `config_blob` (required): LLM configuration object containing:
  - `completion` (required): Completion configuration with:
    - `provider` (required): LLM provider (currently only "openai" supported)
    - `params` (required): **Provider-specific parameters as flexible JSON**
      - For OpenAI Responses API: `model`, `instructions`, `tools`, `temperature`, `metadata`, etc.
      - Structure must match the provider's API specification exactly
      - Stored as-is and passed through to the provider without modification
- `commit_message` (optional): Message describing this initial version

**Example for the config blob: OpenAI Responses API with File Search**

```json
"config_blob": {
    "completion": {
      "provider": "openai",
      "params": {
        "model": "gpt-4o-mini",
        "instructions": "You are a helpful assistant for farming communities...",
        "temperature": 1,
        "tools": [
          {
            "type": "file_search",
            "vector_store_ids": ["vs_692d71f3f5708191b1c46525f3c1e196"],
            "max_num_results": 20
          }]}}}
```

The configuration name must be unique within your project. Once created,
you can create additional versions to track parameter changes while
maintaining the configuration history.
