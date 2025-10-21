"""Model specification registry.

This module provides a centralized registry for managing model specifications.
"""

from typing import Any, Optional

from app.models.llm.specs.base import ModelSpec


class ModelSpecRegistry:
    """Registry for managing model specifications.

    This is a singleton that holds all known model specs and provides
    lookup and validation capabilities.
    """

    _instance: Optional["ModelSpecRegistry"] = None
    _specs: dict[str, ModelSpec] = {}

    def __new__(cls) -> "ModelSpecRegistry":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, spec: ModelSpec) -> None:
        """Register a model specification.

        Args:
            spec: Model specification to register
        """
        key = f"{spec.provider}:{spec.model_name}"
        self._specs[key] = spec

    def get_spec(self, provider: str, model_name: str) -> Optional[ModelSpec]:
        """Get a model specification.

        Args:
            provider: Provider name
            model_name: Model name

        Returns:
            ModelSpec if found, None otherwise
        """
        key = f"{provider}:{model_name}"
        return self._specs.get(key)

    def validate_config(
        self, provider: str, model_name: str, config: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate a configuration against the model spec.

        Args:
            provider: Provider name
            model_name: Model name
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        spec = self.get_spec(provider, model_name)
        if spec is None:
            # If no spec found, we can't validate - allow it through
            # This maintains backward compatibility with models we haven't spec'd yet
            return True, None

        return spec.validate_config(config)

    def list_models(self, provider: Optional[str] = None) -> list[ModelSpec]:
        """List all registered model specs.

        Args:
            provider: Optional provider filter

        Returns:
            List of model specs
        """
        if provider:
            return [spec for spec in self._specs.values() if spec.provider == provider]
        return list(self._specs.values())

    def clear(self) -> None:
        """Clear all registered specs (mainly for testing)."""
        self._specs.clear()


# Global registry instance
model_spec_registry = ModelSpecRegistry()
