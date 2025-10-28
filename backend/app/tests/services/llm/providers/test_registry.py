"""
Tests for the LLM provider registry.
"""
import pytest
from unittest.mock import patch

from sqlmodel import Session
from openai import OpenAI

from app.services.llm.providers.base import BaseProvider
from app.services.llm.providers.openai import OpenAIProvider
from app.services.llm.providers.registry import (
    PROVIDER_REGISTRY,
    get_llm_provider,
    get_supported_providers,
)
from app.tests.utils.utils import get_project


class TestProviderRegistry:
    """Test cases for the PROVIDER_REGISTRY constant."""

    def test_registry_contains_openai(self):
        """Test that registry contains OpenAI provider."""
        assert "openai" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["openai"] == OpenAIProvider

    def test_registry_values_are_provider_classes(self):
        """Test that all registry values are BaseProvider subclasses."""
        for provider_type, provider_class in PROVIDER_REGISTRY.items():
            assert issubclass(
                provider_class, BaseProvider
            ), f"Provider '{provider_type}' class must inherit from BaseProvider"


class TestGetSupportedProviders:
    """Test cases for the get_supported_providers function."""

    def test_get_supported_providers_returns_list(self):
        """Test that get_supported_providers returns a list."""
        result = get_supported_providers()
        assert isinstance(result, list)

    def test_get_supported_providers_matches_registry_keys(self):
        """Test that supported providers matches registry keys."""
        result = get_supported_providers()
        assert set(result) == set(PROVIDER_REGISTRY.keys())


class TestGetLLMProvider:
    """Test cases for the get_llm_provider function."""

    def test_get_llm_provider_with_openai(self, db: Session):
        """Test getting OpenAI provider successfully."""
        project = get_project(db)

        with patch(
            "app.services.llm.providers.registry.get_provider_credential"
        ) as mock_get_creds:
            mock_get_creds.return_value = {"api_key": "test-api-key"}

            provider = get_llm_provider(
                session=db,
                provider_type="openai",
                project_id=project.id,
                organization_id=project.organization_id,
            )

            assert isinstance(provider, OpenAIProvider)
            assert isinstance(provider.client, OpenAI)
            mock_get_creds.assert_called_once_with(
                session=db,
                provider="openai",
                project_id=project.id,
                org_id=project.organization_id,
            )

            mock_get_creds.return_value = {"wrong_key": "value"}
            with pytest.raises(ValueError) as exc_info:
                get_llm_provider(
                    session=db,
                    provider_type="openai",
                    project_id=project.id,
                    organization_id=project.organization_id,
                )
            assert "OpenAI credentials not configured for this project." in str(
                exc_info.value
            )

    def test_get_llm_provider_with_invalid_provider(self, db: Session):
        """Test that invalid provider type raises ValueError."""
        project = get_project(db)

        with pytest.raises(ValueError) as exc_info:
            get_llm_provider(
                session=db,
                provider_type="invalid_provider",
                project_id=project.id,
                organization_id=project.organization_id,
            )

        error_message = str(exc_info.value)
        assert "invalid_provider" in error_message
        assert "is not supported" in error_message
        assert "openai" in error_message

    def test_get_llm_provider_with_missing_credentials(self, db: Session):
        """Test handling of errors when credentials are not found."""
        project = get_project(db)

        with patch(
            "app.services.llm.providers.registry.get_provider_credential"
        ) as mock_get_creds:
            mock_get_creds.return_value = None

            with pytest.raises(ValueError) as exc_info:
                get_llm_provider(
                    session=db,
                    provider_type="openai",
                    project_id=project.id,
                    organization_id=project.organization_id,
                )

            assert "not configured for this project" in str(exc_info.value)
