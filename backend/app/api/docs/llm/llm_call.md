Make an LLM API call using either a stored configuration or an ad-hoc configuration.

This endpoint initiates an asynchronous LLM call job. The request is queued
for processing, and results are delivered via the callback URL when complete.

### Request Fields

**`query`** (required) - Query parameters for this LLM call:
- `input` (required, string, min 1 char): User question/prompt/query
- `conversation` (optional, object): Conversation configuration
  - `id` (optional, string): Existing conversation ID to continue
  - `auto_create` (optional, boolean, default false): Create new conversation if no ID provided
  - **Note**: Cannot specify both `id` and `auto_create=true`

**`config`** (required) - Configuration for the LLM call (choose one mode):

- **Mode 1: Stored Configuration**
  - `id` (UUID): Configuration ID
  - `version` (integer >= 1): Version number
  - **Both required together**
  - **Note**: When using stored configuration, do not include the `blob` field in the request body

- **Mode 2: Ad-hoc Configuration**
  - `blob` (object): Complete configuration object (see Create Config endpoint documentation for examples)
    - `completion` (required):
      - `provider` (required, string): Currently only "openai"
      - `params` (required, object): Provider-specific parameters (flexible JSON)
  - **Note**: When using ad-hoc configuration, do not include `id` and `version` fields

**`callback_url`** (optional, HTTPS URL):
- Webhook endpoint to receive the response
- Must be a valid HTTPS URL
- If not provided, response is only accessible through job status

**`include_provider_raw_response`** (optional, boolean, default false):
- When true, includes the unmodified raw response from the LLM provider

**`request_metadata`** (optional, object):
- Custom JSON metadata
- Passed through unchanged in the response

---
