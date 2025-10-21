# LLM API Specification-Driven Architecture

## Overview

The LLM API now uses a **specification-driven architecture** that separates concerns between:

1. **Model Specifications** - Define what each model supports
2. **Transformation Layer** - Convert unified API to provider-specific formats
3. **Validation** - Automatic validation against model specs
4. **Providers** - Execute API calls using transformed configurations

This architecture eliminates the need for `build_params` logic in providers and centralizes configuration management.

## Architecture Components

### 1. Model Specifications (`app/models/llm/model_spec.py`)

Model specifications are the **single source of truth** for what each LLM model supports.

```python
from app.models.llm.model_spec import ModelSpec, ModelCapabilities, ParameterSpec

spec = ModelSpec(
    model_name="gpt-4",
    provider="openai",
    capabilities=ModelCapabilities(
        supports_file_search=True,
        supports_function_calling=True,
        supports_streaming=True,
    ),
    parameters=[
        ParameterSpec(
            name="temperature",
            type="float",
            min_value=0.0,
            max_value=2.0,
            default=1.0,
        ),
        ParameterSpec(
            name="max_tokens",
            type="int",
            min_value=1,
            max_value=128000,
        ),
    ],
)
```

**Key Features:**
- Declarative capability flags
- Parameter type and range constraints
- Automatic validation via `validate_config()`
- Feature detection via `supports_feature()`

### 2. Model Registry (`ModelSpecRegistry`)

The global registry manages all model specifications:

```python
from app.models.llm.model_spec import model_spec_registry

# Register a spec
model_spec_registry.register(spec)

# Get a spec
spec = model_spec_registry.get_spec("openai", "gpt-4")

# Validate config
is_valid, error = model_spec_registry.validate_config(
    "openai", "gpt-4", {"temperature": 0.7}
)
```

### 3. Transformation Layer (`app/services/llm/transformer.py`)

Transformers convert the unified API contract to provider-specific formats:

```python
from app.services.llm.transformer import OpenAITransformer, TransformerFactory

# Create transformer
transformer = TransformerFactory.create_transformer(
    provider="openai",
    model_name="gpt-4",
    use_spec=True,  # Enable validation
)

# Transform and validate
params = transformer.validate_and_transform(request)
```

**Available Transformers:**
- `OpenAITransformer` - OpenAI Responses API format
- `AnthropicTransformer` - Anthropic Messages API format
- `GoogleTransformer` - Google Generative AI format
- `AzureOpenAITransformer` - Azure OpenAI (same as OpenAI)

### 4. Updated Provider Interface (`BaseProvider`)

Providers now use transformers automatically:

```python
class BaseProvider(ABC):
    def __init__(self, client: Any, transformer: Optional[ConfigTransformer] = None):
        self.client = client
        self.transformer = transformer

    def build_params(self, request: LLMCallRequest) -> dict[str, Any]:
        """Uses transformer to build params with automatic validation."""
        transformer = self._get_transformer(request)
        return transformer.validate_and_transform(request)
```

## Request Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. API Request: LLMCallRequest                                  │
│    - Unified API contract                                        │
│    - Provider + model specified                                  │
│    - Standard parameters (temp, max_tokens, etc.)                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Provider Detection                                            │
│    - Extract provider type from request                          │
│    - Create provider instance via ProviderFactory                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Transformer Creation                                          │
│    - TransformerFactory creates appropriate transformer          │
│    - Loads model spec from registry (if available)               │
│    - Transformer initialized with spec for validation            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Config Validation                                             │
│    - Extract parameters from request                             │
│    - Validate against model spec:                                │
│      ✓ Type checking (int, float, str, bool)                     │
│      ✓ Range validation (min/max values)                         │
│      ✓ Allowed values (e.g., "low"/"medium"/"high")              │
│      ✓ Required parameter checking                               │
│    - Raise ValueError if validation fails                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Transformation                                                │
│    - Convert unified API to provider format:                     │
│      • OpenAI: {model, input, temperature, ...}                  │
│      • Anthropic: {model, messages, max_tokens, ...}             │
│      • Google: {model, contents, generation_config, ...}         │
│    - Add provider-specific features (reasoning, tools, etc.)     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. Provider Execution                                            │
│    - Provider calls build_params() (uses transformer)            │
│    - Makes API call to LLM provider                              │
│    - Returns standardized LLMCallResponse                        │
└─────────────────────────────────────────────────────────────────┘
```

## OpenAI Model Specifications

Pre-configured specs for OpenAI models are in `app/services/llm/specs/openai_specs.py`:

**Standard Models:**
- GPT-4 series: `gpt-4`, `gpt-4-turbo`, `gpt-4o`, `gpt-4o-mini`
- GPT-3.5 series: `gpt-3.5-turbo`, `gpt-3.5-turbo-16k`

**O-series Models (Reasoning):**
- `o1`, `o1-preview`, `o1-mini`
- `o3`, `o3-mini`
- Support reasoning configuration and text verbosity

**Capabilities by Model:**

| Model | File Search | Functions | Streaming | Vision | Reasoning |
|-------|-------------|-----------|-----------|--------|-----------|
| GPT-4 | ✓ | ✓ | ✓ | ✗ | ✗ |
| GPT-4o | ✓ | ✓ | ✓ | ✓ | ✗ |
| GPT-3.5 | ✓ | ✓ | ✓ | ✗ | ✗ |
| O-series | ✓ | ✗ | ✓ | ✗ | ✓ |

## Adding New Model Specs

### Option 1: Add to Existing Provider Specs

Edit `app/services/llm/specs/openai_specs.py` (or create new provider spec file):

```python
def create_new_model_specs() -> list[ModelSpec]:
    specs = []

    specs.append(
        ModelSpec(
            model_name="new-model",
            provider="provider-name",
            capabilities=ModelCapabilities(
                supports_streaming=True,
                # ... other capabilities
            ),
            parameters=[
                ParameterSpec(
                    name="temperature",
                    type="float",
                    min_value=0.0,
                    max_value=1.0,
                ),
                # ... other parameters
            ],
        )
    )

    return specs
```

### Option 2: Register Dynamically at Runtime

```python
from app.models.llm.model_spec import model_spec_registry, ModelSpec

spec = ModelSpec(...)
model_spec_registry.register(spec)
```

## Adding New Providers

### Step 1: Create Provider Transformer

```python
# app/services/llm/transformer.py

class NewProviderTransformer(ConfigTransformer):
    """Transformer for NewProvider API format."""

    def transform(self, request: LLMCallRequest) -> dict[str, Any]:
        """Transform to NewProvider API format."""
        model_spec = request.llm.llm_model_spec

        params = {
            "model": model_spec.model,
            # ... provider-specific format
        }

        # Add parameters
        if model_spec.temperature is not None:
            params["temperature"] = model_spec.temperature

        return params
```

### Step 2: Register Transformer

```python
# In TransformerFactory
_TRANSFORMERS = {
    "openai": OpenAITransformer,
    "anthropic": AnthropicTransformer,
    "google": GoogleTransformer,
    "newprovider": NewProviderTransformer,  # Add here
}
```

### Step 3: Create Provider Implementation

```python
# app/services/llm/newprovider_provider.py

class NewProviderProvider(BaseProvider):
    """NewProvider implementation."""

    def execute(self, request: LLMCallRequest) -> tuple[LLMCallResponse | None, str | None]:
        try:
            # build_params() uses transformer automatically
            params = self.build_params(request)

            # Make API call
            response = self.client.generate(**params)

            # Return standardized response
            return LLMCallResponse(...), None
        except Exception as e:
            return None, str(e)
```

### Step 4: Register Provider

```python
# app/services/llm/provider_factory.py

_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "newprovider": NewProviderProvider,  # Add here
}
```

### Step 5: Create Model Specs

```python
# app/services/llm/specs/newprovider_specs.py

def create_newprovider_specs() -> list[ModelSpec]:
    return [
        ModelSpec(
            model_name="newprovider-model-1",
            provider="newprovider",
            capabilities=ModelCapabilities(...),
            parameters=[...],
        ),
    ]

def register_newprovider_specs() -> None:
    specs = create_newprovider_specs()
    for spec in specs:
        model_spec_registry.register(spec)
```

### Step 6: Initialize Specs

```python
# app/services/llm/specs/__init__.py

from app.services.llm.specs.newprovider_specs import register_newprovider_specs

def initialize_model_specs() -> None:
    register_openai_specs()
    register_newprovider_specs()  # Add here
```

## Configuration Validation Examples

### Valid Configuration

```python
request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Hello",
        llm_model_spec=LLMModelSpec(
            model="gpt-4",
            provider="openai",
            temperature=0.7,  # ✓ Within range [0.0, 2.0]
            max_tokens=1000,  # ✓ Within range [1, 128000]
        ),
    ),
)
# ✓ Passes validation
```

### Invalid Configuration (Out of Range)

```python
request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Hello",
        llm_model_spec=LLMModelSpec(
            model="gpt-4",
            provider="openai",
            temperature=5.0,  # ✗ Out of range [0.0, 2.0]
        ),
    ),
)
# ✗ Raises ValueError: "Parameter 'temperature' must be <= 2.0"
```

### Invalid Configuration (Wrong Type)

```python
request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Hello",
        llm_model_spec=LLMModelSpec(
            model="gpt-4",
            provider="openai",
            temperature="high",  # ✗ Should be float
        ),
    ),
)
# ✗ Raises ValueError: "Parameter 'temperature' must be a number"
```

### O-series Model Configuration

```python
request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Complex reasoning task",
        llm_model_spec=LLMModelSpec(
            model="o3-mini",
            provider="openai",
            temperature=0.5,
            reasoning=ReasoningConfig(effort="high"),  # ✓ Valid: "low", "medium", "high"
            text=TextConfig(verbosity="medium"),
        ),
    ),
)
# ✓ Passes validation
```

## Benefits of This Architecture

### 1. Separation of Concerns
- **Model Specs**: Define capabilities
- **Transformers**: Handle format conversion
- **Providers**: Execute API calls
- **Validation**: Centralized in specs

### 2. Maintainability
- Add new models by adding specs (no code changes)
- Add new providers by implementing transformer
- Validation logic in one place

### 3. Type Safety
- Compile-time type checking
- Runtime validation against specs
- Clear error messages

### 4. Extensibility
- Easy to add new providers
- Easy to add new models
- Runtime spec registration

### 5. Testability
- Test specs independently
- Test transformers independently
- Test providers independently
- Mock transformers for provider tests

## Migration Guide

### Before (Old Architecture)

```python
class OpenAIProvider(BaseProvider):
    def build_params(self, request: LLMCallRequest) -> dict[str, Any]:
        # Manual parameter building
        params = {
            "model": request.llm.llm_model_spec.model,
            "input": [{"role": "user", "content": request.llm.prompt}],
        }

        # Manual parameter handling
        if request.llm.llm_model_spec.temperature is not None:
            params["temperature"] = request.llm.llm_model_spec.temperature

        # No validation!
        return params
```

### After (New Architecture)

```python
class OpenAIProvider(BaseProvider):
    # build_params() inherited from BaseProvider
    # Automatically uses OpenAITransformer
    # Automatic validation via model specs
    pass
```

The `build_params()` method is now in `BaseProvider` and automatically:
1. Creates appropriate transformer
2. Validates configuration against model spec
3. Transforms to provider format
4. Raises clear errors if validation fails

## Testing

Run the architecture test:

```bash
uv run python test_specs_only.py
```

Expected output:
```
Testing Core Specification and Transformation Logic
======================================================================

1. Model Specification...
✓ Valid config: True
✓ Invalid config rejected: True

2. Transformers...
✓ OpenAI transform: model=gpt-4, temp=0.7
✓ O-series transform: reasoning={'effort': 'high'}
✓ Anthropic transform: model=claude-3-opus, max_tokens=1024

3. OpenAI Model Specs...
✓ Created 12 OpenAI model specs
✓ GPT-4 spec: gpt-4, params=['temperature', 'max_tokens', 'top_p']

4. Spec-based Validation...
✓ Valid O-series config passed validation
✓ Invalid config correctly rejected

======================================================================
SUCCESS: Core architecture works correctly!
======================================================================
```

## Future Enhancements

1. **Database-backed Specs**: Store model specs in database for dynamic updates
2. **Spec Versioning**: Version model specs for backward compatibility
3. **Capability Discovery**: API endpoint to list available models and capabilities
4. **Advanced Validation**: Custom validators, cross-parameter validation
5. **Streaming Support**: Add streaming capability to transformers
6. **Function Calling**: Unified function calling across providers
7. **Cost Tracking**: Add pricing info to model specs
