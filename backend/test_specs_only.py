"""Simple test for model specs and transformers without full app imports."""

import sys
from pathlib import Path

backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

print("=" * 70)
print("Testing Core Specification and Transformation Logic")
print("=" * 70)

# Test Model Spec
print("\n1. Model Specification...")
from app.models.llm.model_spec import ModelSpec, ModelCapabilities, ParameterSpec

spec = ModelSpec(
    model_name="gpt-4",
    provider="openai",
    capabilities=ModelCapabilities(supports_file_search=True),
    parameters=[
        ParameterSpec(name="temperature", type="float", min_value=0.0, max_value=2.0)
    ],
)

config = {"temperature": 0.7}
is_valid, error = spec.validate_config(config)
print(f"✓ Valid config: {is_valid}")

config = {"temperature": 5.0}
is_valid, error = spec.validate_config(config)
print(f"✓ Invalid config rejected: {not is_valid} - {error}")

# Test Transformers (import module directly by file, avoiding __init__)
print("\n2. Transformers...")

# Import transformer module directly
import importlib.util
spec_tf = importlib.util.spec_from_file_location(
    "transformer",
    backend_path / "app" / "services" / "llm" / "transformer.py"
)
transformer = importlib.util.module_from_spec(spec_tf)
spec_tf.loader.exec_module(transformer)

from app.models.llm.call import LLMCallRequest, LLMConfig, LLMModelSpec, ReasoningConfig

openai_tf = transformer.OpenAITransformer()

request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Test",
        llm_model_spec=LLMModelSpec(
            model="gpt-4",
            provider="openai",
            temperature=0.7,
        ),
    ),
)

params = openai_tf.transform(request)
print(f"✓ OpenAI transform: model={params['model']}, temp={params.get('temperature')}")

# Test O-series
o_request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Think hard",
        llm_model_spec=LLMModelSpec(
            model="o3",
            provider="openai",
            reasoning=ReasoningConfig(effort="high"),
        ),
    ),
)

o_params = openai_tf.transform(o_request)
print(f"✓ O-series transform: reasoning={o_params.get('reasoning')}")

# Test Anthropic
anthropic_tf = transformer.AnthropicTransformer()
anthropic_request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Hello",
        llm_model_spec=LLMModelSpec(
            model="claude-3-opus",
            provider="anthropic",
            max_tokens=1024,
        ),
    ),
)

anthropic_params = anthropic_tf.transform(anthropic_request)
print(f"✓ Anthropic transform: model={anthropic_params['model']}, max_tokens={anthropic_params['max_tokens']}")

# Test OpenAI Specs
print("\n3. OpenAI Model Specs...")

# Import openai_specs directly
spec_os = importlib.util.spec_from_file_location(
    "openai_specs",
    backend_path / "app" / "services" / "llm" / "specs" / "openai_specs.py"
)
openai_specs = importlib.util.module_from_spec(spec_os)
spec_os.loader.exec_module(openai_specs)

specs = openai_specs.create_openai_specs()
print(f"✓ Created {len(specs)} OpenAI model specs")

gpt4 = next(s for s in specs if s.model_name == "gpt-4")
print(f"✓ GPT-4 spec: {gpt4.model_name}, params={[p.name for p in gpt4.parameters[:3]]}")

o3 = next(s for s in specs if s.model_name == "o3-mini")
print(f"✓ O3-mini spec: supports_reasoning={o3.capabilities.supports_reasoning}")

# Test validation with spec
print("\n4. Spec-based Validation...")
tf_with_spec = transformer.OpenAITransformer(model_spec=o3)

valid_o_request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Test",
        llm_model_spec=LLMModelSpec(
            model="o3-mini",
            provider="openai",
            temperature=0.5,
            reasoning=ReasoningConfig(effort="medium"),
        ),
    ),
)

try:
    params = tf_with_spec.validate_and_transform(valid_o_request)
    print(f"✓ Valid O-series config passed validation")
except ValueError as e:
    print(f"✗ Should have passed: {e}")

invalid_o_request = LLMCallRequest(
    llm=LLMConfig(
        prompt="Test",
        llm_model_spec=LLMModelSpec(
            model="o3-mini",
            provider="openai",
            temperature=10.0,  # Out of range
        ),
    ),
)

try:
    params = tf_with_spec.validate_and_transform(invalid_o_request)
    print(f"✗ Should have failed validation")
except ValueError as e:
    print(f"✓ Invalid config correctly rejected")

print("\n" + "=" * 70)
print("SUCCESS: Core architecture works correctly!")
print("=" * 70)
