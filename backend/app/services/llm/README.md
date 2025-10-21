# LLM Service Module

A provider-agnostic interface for executing LLM calls. Currently supports OpenAI with an extensible architecture for future providers.

## Architecture

The LLM service follows a layered architecture with clear separation of concerns:

```
app/
├── models/llm/                    # Data models
│   ├── call.py                    # Database models
│   ├── config.py                  # Configuration models
│   ├── request.py                 # Request models
│   ├── response.py                # Response models
│   └── specs/                     # Model specifications
│       ├── base.py                # Base spec classes
│       └── registry.py            # Spec registry
│
└── services/llm/                  # Service layer
    ├── __init__.py                # Public API
    ├── constants.py               # Constants and enums
    ├── exceptions.py              # Custom exceptions
    ├── orchestrator.py            # Main entry point
    ├── jobs.py                    # Celery job management
    │
    ├── providers/                 # Provider implementations
    │   ├── base.py                # Abstract base provider
    │   ├── factory.py             # Provider factory (extensible)
    │   └── openai.py              # OpenAI implementation
    │
    ├── transformers/              # Request transformers
    │   ├── base.py                # Abstract transformer
    │   ├── factory.py             # Transformer factory (extensible)
    │   └── openai.py              # OpenAI transformer
    │
    └── specs/                     # Model specifications
        ├── __init__.py            # Spec initialization
        └── openai.py              # OpenAI model specs
```

## Key Components

### 1. Orchestration Layer

**`orchestrator.py`** - Main entry point for LLM calls
- Routes requests to appropriate providers
- Handles error handling and logging
- Provider-agnostic interface

**`jobs.py`** - Celery job management
- Asynchronous job execution
- Job status tracking
- Integration with job queue

### 2. Provider Layer

**`BaseProvider`** - Abstract base class for all providers
- Defines standard interface
- Handles transformer integration
- Manages parameter building

**`OpenAIProvider`** - OpenAI implementation
- GPT-4, GPT-3.5 models
- O-series reasoning models
- Vector store file search
- Full feature support

**`ProviderFactory`** - Creates provider instances
- Supports provider registration for extensibility
- Runtime provider addition
- Currently registered: OpenAI

### 3. Transformation Layer

**`ConfigTransformer`** - Base transformer class
- Converts unified API to provider format
- Validates against model specs
- Extensible for new providers

**`OpenAITransformer`** - OpenAI transformation
- Handles OpenAI Responses API format
- Supports reasoning configuration
- Vector store integration

**`TransformerFactory`** - Creates transformer instances
- Loads model specs automatically
- Supports custom transformers

### 4. Specification Layer

**`ModelSpec`** - Model specification class
- Defines capabilities (reasoning, vision, etc.)
- Parameter constraints and validation
- Feature detection

**`ModelSpecRegistry`** - Singleton registry
- Manages all model specs
- Provides lookup and validation
- Centralized spec storage

### 5. Error Handling

Custom exception hierarchy:
- `LLMServiceError` - Base exception
- `ProviderError` - Provider-specific errors
- `UnsupportedProviderError` - Unsupported provider
- `ValidationError` - Configuration validation
- `TransformationError` - Transformation failures
- `APICallError` - API call failures

## Usage

### Basic LLM Call

```python
from app.services.llm import execute_llm_call
from app.models.llm import LLMCallRequest, LLMConfig, LLMModelSpec

# Create request
request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Explain quantum computing",
        llm_model_spec=LLMModelSpec(
            model="gpt-4",
            provider="openai",
            temperature=0.7,
            max_tokens=500
        )
    )
)

# Execute call
response, error = execute_llm_call(request, openai_client)

if response:
    print(f"Response: {response.message}")
    print(f"Tokens: {response.total_tokens}")
else:
    print(f"Error: {error}")
```

### With Vector Store (RAG)

```python
request = LLMCallRequest(
    llm=LLMConfig(
        prompt="What does the documentation say about authentication?",
        vector_store_id="vs_abc123",
        llm_model_spec=LLMModelSpec(
            model="gpt-4",
            provider="openai"
        )
    ),
    max_num_results=10
)

response, error = execute_llm_call(request, openai_client)

# Access file search results
if response and response.file_search_results:
    for result in response.file_search_results:
        print(f"Score: {result['score']}, Text: {result['text']}")
```

### O-Series Models (Reasoning)

```python
from app.models.llm import ReasoningConfig, TextConfig

request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Solve this complex problem...",
        llm_model_spec=LLMModelSpec(
            model="o1",
            provider="openai",
            reasoning=ReasoningConfig(effort="high"),
            text=TextConfig(verbosity="medium")
        )
    )
)

response, error = execute_llm_call(request, openai_client)
```

### Asynchronous Job

```python
from app.services.llm.jobs import start_job

# Schedule background job
job_id = start_job(
    db=session,
    request=request,
    project_id=123,
    organization_id=456
)

# Job runs asynchronously via Celery
print(f"Job scheduled: {job_id}")
```

## Adding New Providers

### 1. Create Provider Implementation

```python
# app/services/llm/providers/anthropic.py
from app.services.llm.providers.base import BaseProvider
from app.models.llm import LLMCallRequest, LLMCallResponse

class AnthropicProvider(BaseProvider):
    def execute(self, request: LLMCallRequest) -> tuple[LLMCallResponse | None, str | None]:
        params = self.build_params(request)
        response = self.client.messages.create(**params)
        # Process response...
        return llm_response, None
```

### 2. Create Transformer

```python
# app/services/llm/transformers/anthropic.py
from app.services.llm.transformers.base import ConfigTransformer

class AnthropicTransformer(ConfigTransformer):
    def transform(self, request: LLMCallRequest) -> dict[str, Any]:
        return {
            "model": request.llm.llm_model_spec.model,
            "messages": [{"role": "user", "content": request.llm.prompt}],
            "max_tokens": request.llm.llm_model_spec.max_tokens or 1024,
            # ... other Anthropic-specific params
        }
```

### 3. Create Model Specs

```python
# app/services/llm/specs/anthropic.py
from app.models.llm.specs import ModelSpec, ModelCapabilities, ParameterSpec

def create_anthropic_specs() -> list[ModelSpec]:
    return [
        ModelSpec(
            model_name="claude-3-opus",
            provider="anthropic",
            capabilities=ModelCapabilities(
                supports_streaming=True,
                supports_vision=True,
                # ...
            ),
            parameters=[
                ParameterSpec(name="temperature", type="float", min_value=0.0, max_value=1.0),
                # ...
            ]
        )
    ]
```

### 4. Register Components

```python
# Update factories
from app.services.llm.providers.factory import ProviderFactory
from app.services.llm.transformers.factory import TransformerFactory

ProviderFactory.register_provider("anthropic", AnthropicProvider)
TransformerFactory.register_transformer("anthropic", AnthropicTransformer)
```

## Configuration

### Constants

Edit `constants.py` to update default values:

```python
DEFAULT_TEMPERATURE = 1.0
DEFAULT_TOP_P = 1.0
DEFAULT_MAX_RESULTS = 20
```

### Supported Providers

Currently supported: `openai`

The architecture is designed to be extensible. Future providers can be added following the pattern in "Adding New Providers" section.

## Testing

```python
# Test with mock client
from unittest.mock import Mock

mock_client = Mock()
mock_client.responses.create.return_value = Mock(
    id="resp_123",
    output_text="Test response",
    model="gpt-4",
    usage=Mock(input_tokens=10, output_tokens=20, total_tokens=30)
)

response, error = execute_llm_call(request, mock_client)
assert response.message == "Test response"
```

## Best Practices

1. **Always use model specs** - Enable validation for production code
2. **Handle errors gracefully** - Check for both response and error
3. **Use type hints** - Maintain type safety throughout
4. **Log appropriately** - Use structured logging for debugging
5. **Follow the architecture** - Don't bypass the abstraction layers
6. **Add tests** - Test new providers and transformers thoroughly

## Future Enhancements

- [ ] Streaming response support
- [ ] Function calling for all providers
- [ ] Batch request processing
- [ ] Response caching
- [ ] Rate limiting
- [ ] Cost tracking
- [ ] Provider failover
- [ ] A/B testing between providers

## Troubleshooting

### Common Issues

**Import errors after refactoring**
- Ensure old files are removed
- Check `__init__.py` exports
- Clear Python cache: `find . -type d -name __pycache__ -exec rm -r {} +`

**Validation errors**
- Check model spec definitions
- Verify parameter constraints
- Use `model_spec.validate_config()` for debugging

**Provider not found**
- Ensure provider is registered in factory
- Check provider name spelling
- Verify provider is in `SUPPORTED_PROVIDERS`

## Contributing

When adding new features:
1. Update relevant specs
2. Add comprehensive docstrings
3. Update this README
4. Add tests
5. Follow existing patterns
