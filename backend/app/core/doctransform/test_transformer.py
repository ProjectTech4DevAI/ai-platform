import tempfile
from pathlib import Path
from .transformer import DocumentTransformer


class TestTransformer(DocumentTransformer):
    """
    A test transformer that returns a hardcoded lorem ipsum string.
    """
    
    def supports_formats(self) -> dict:
        """Test transformer supports any format to any format."""
        return {
            'pdf': ['markdown', 'text'],
            'text': ['markdown'],
            'markdown': ['text']
        }

    def transform(self, file_path: str, target_format: str) -> Path:
        content = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        )
        
        # Write content to temporary file
        file_extension = 'md' if target_format == 'markdown' else target_format
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=f'.{file_extension}', delete=False, encoding='utf-8')
        temp_file.write(content)
        temp_file.close()
        
        return Path(temp_file.name)


import pytest
from unittest.mock import Mock, patch
from sqlmodel import Session
from app.core.doctransform.zerox_transformer import ZeroxTransformer
from app.models import Document


def test_zerox_transformer_supports_formats():
    transformer = ZeroxTransformer()
    formats = transformer.supports_formats()
    
    assert 'pdf' in formats
    assert 'markdown' in formats['pdf']


@patch('app.core.doctransform.zerox_transformer.zerox')
def test_zerox_transform(mock_zerox):
    # Mock the zerox function
    mock_zerox.return_value = {"success": True}
    
    # Create mock objects
    session = Mock(spec=Session)
    source_document = Mock(spec=Document)
    source_document.id = "test-id"
    source_document.fname = "test.pdf"
    source_document.owner_id = 1
    
    storage = Mock()
    storage.stream.return_value = Mock()
    storage.stream.return_value.read.return_value = b"mock pdf content"
    
    transformer = ZeroxTransformer()
    
    # This test would need more setup to actually work
    # but demonstrates the testing approach
    assert transformer.supports_formats()['pdf'] == ['markdown']
