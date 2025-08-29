"""
Test organization and base classes for DocTransform service tests.

This module contains:
- DocTransformTestBase: Base test class with common setup
- TestDataProvider: Common test data and configurations
- MockHelpers: Utilities for creating mocks and test fixtures

All fixtures are automatically available from conftest.py in the same directory.
Test files can import these base classes and use fixtures without additional imports.
"""
from typing import List
from urllib.parse import urlparse

from app.core.cloud import AmazonCloudStorageClient
from app.core.config import settings
from app.models import Document, Project


class DocTransformTestBase:
    """Base class for document transformation tests with common setup and utilities."""
    
    def setup_aws_s3(self) -> AmazonCloudStorageClient:
        """Setup AWS S3 for testing."""
        aws = AmazonCloudStorageClient()
        aws.create()
        return aws
    
    def create_s3_document_content(
        self, 
        aws: AmazonCloudStorageClient, 
        project: Project, 
        document: Document, 
        content: bytes = b"Test document content"
    ) -> bytes:
        """Create content in S3 for a document."""
        parsed_url = urlparse(document.object_store_url)
        s3_key = parsed_url.path.lstrip('/')
        
        aws.client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=content
        )
        return content
    
    def verify_s3_content(
        self, 
        aws: AmazonCloudStorageClient, 
        project: Project, 
        transformed_doc: Document,
        expected_content: str = None
    ) -> None:
        """Verify the content stored in S3."""
        if expected_content is None:
            expected_content = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        
        parsed_url = urlparse(transformed_doc.object_store_url)

        transformed_key = parsed_url.path.lstrip('/')
        
        response = aws.client.get_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=transformed_key
        )
        transformed_content = response['Body'].read().decode('utf-8')
        assert transformed_content == expected_content


class TestDataProvider:
    """Provides test data and configurations for document transformation tests."""
    
    @staticmethod
    def get_format_test_cases() -> List[tuple]:
        """Get test cases for different document formats."""
        return [
            ("markdown", ".md"),
            ("text", ".txt"),
            ("html", ".html"),
        ]
    
    @staticmethod
    def get_content_type_test_cases() -> List[tuple]:
        """Get test cases for content types and extensions."""
        return [
            ("markdown", "text/markdown", ".md"),
            ("text", "text/plain", ".txt"),
            ("html", "text/html", ".html"),
            ("unknown", "text/plain", ".unknown")  # Default fallback
        ]
    
    @staticmethod
    def get_test_transformer_names() -> List[str]:
        """Get list of test transformer names."""
        return ["test"]

    @staticmethod
    def get_sample_document_content() -> bytes:
        """Get sample document content for testing."""
        return b"This is a test document for transformation."


class MockHelpers:
    """Helper methods for creating mocks in tests."""
    
    @staticmethod
    def create_failing_convert_document(fail_count: int = 1):
        """Create a side effect function that fails specified times then succeeds."""
        call_count = 0
        def failing_convert_document(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= fail_count:
                raise Exception("Transient error")
            return "Success after retries"
        return failing_convert_document
    
    @staticmethod
    def create_persistent_failing_convert_document(error_message: str = "Persistent error"):
        """Create a side effect function that always fails."""
        def persistent_failing_convert_document(*args, **kwargs):
            raise Exception(error_message)
        return persistent_failing_convert_document
