"""LLM services module.

This module provides a provider-agnostic interface for executing LLM calls.
Currently supports OpenAI with an extensible architecture for future providers.

Architecture:
-----------
The LLM service follows a layered architecture with clear separation of concerns:

1. **Models Layer** (`app.models.llm`)
   - Request/Response models
   - Configuration models
   - Model specifications

2. **Orchestration Layer**
   - `orchestrator.py`: Main entry point for LLM calls
   - `jobs.py`: Celery job management

3. **Provider Layer** (`providers/`)
   - `base.py`: Abstract base provider
   - `openai.py`: OpenAI implementation
   - `factory.py`: Provider factory (extensible)

4. **Transformation Layer** (`transformers/`)
   - `base.py`: Abstract transformer
   - `openai.py`: OpenAI transformer
   - `factory.py`: Transformer factory (extensible)

5. **Specification Layer** (`specs/`)
   - `openai.py`: OpenAI model specs
   - Model capability definitions
   - Parameter validation rules

Key Components:
--------------
- execute_llm_call: Main entry point for LLM API calls
- BaseProvider: Abstract base class for all providers
- ConfigTransformer: Base class for request transformation
- ModelSpec: Model specification with validation
- ProviderFactory: Factory for creating provider instances
- TransformerFactory: Factory for creating transformers

The architecture uses specification-driven configuration with:
1. Model specs defining capabilities and parameter constraints
2. Transformers converting unified API contracts to provider-specific formats
3. Automatic validation against model specifications
4. Custom exceptions for better error handling

Usage Example:
-------------
```python
from app.services.llm import execute_llm_call
from app.models.llm import LLMCallRequest, LLMConfig, LLMModelSpec

request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Hello, world!",
        llm_model_spec=LLMModelSpec(
            model="gpt-4",
            provider="openai",
            temperature=0.7
        )
    )
)

response, error = execute_llm_call(request, openai_client)
```
"""

# Main orchestration
from app.services.llm.orchestrator import execute_llm_call

# Providers
from app.services.llm.providers import (
    BaseProvider,
    ProviderFactory,
    OpenAIProvider,
)

# Transformers
from app.services.llm.transformers import (
    ConfigTransformer,
    TransformerFactory,
    OpenAITransformer,
)

# Constants and exceptions
from app.services.llm.constants import (
    ProviderType,
    EffortLevel,
    VerbosityLevel,
    SUPPORTED_PROVIDERS,
)
from app.services.llm.exceptions import (
    LLMServiceError,
    ProviderError,
    UnsupportedProviderError,
    ValidationError,
    TransformationError,
    APICallError,
)

# Initialize model specs on module import
import app.services.llm.specs  # noqa: F401

__all__ = [
    # Main entry point
    "execute_llm_call",
    # Providers
    "BaseProvider",
    "ProviderFactory",
    "OpenAIProvider",
    # Transformers
    "ConfigTransformer",
    "TransformerFactory",
    "OpenAITransformer",
    # Constants
    "ProviderType",
    "EffortLevel",
    "VerbosityLevel",
    "SUPPORTED_PROVIDERS",
    # Exceptions
    "LLMServiceError",
    "ProviderError",
    "UnsupportedProviderError",
    "ValidationError",
    "TransformationError",
    "APICallError",
]
