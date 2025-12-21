import asyncio
from unittest.mock import Mock, patch

import pytest

from app.services.doctransform.zerox_transformer import ZeroxTransformer
from app.services.doctransform.transformer import Transformer


def create_async_mock(return_value):
    """Helper to create an async function that returns a value."""

    async def async_func(*args, **kwargs):
        return return_value

    return async_func


class TestZeroxTransformerInit:
    """Test ZeroxTransformer initialization."""

    def test_init_default_model(self):
        """Test initialization with default model."""
        transformer = ZeroxTransformer()
        assert transformer.model == "gpt-4o"

    def test_init_custom_model(self):
        """Test initialization with custom model."""
        transformer = ZeroxTransformer(model="gpt-4o-mini")
        assert transformer.model == "gpt-4o-mini"

    def test_init_different_models(self):
        """Test initialization with various model names."""
        models = ["gpt-4", "gpt-3.5-turbo", "claude-3-opus"]
        for model in models:
            transformer = ZeroxTransformer(model=model)
            assert transformer.model == model


class TestZeroxTransformerTransform:
    """Test ZeroxTransformer.transform method."""

    @pytest.fixture
    def temp_input_file(self, tmp_path):
        """Create a temporary input file."""
        input_file = tmp_path / "test_input.pdf"
        input_file.write_bytes(b"PDF content")
        return input_file

    @pytest.fixture
    def temp_output_file(self, tmp_path):
        """Create a temporary output file path."""
        return tmp_path / "test_output.txt"

    @pytest.fixture
    def mock_zerox_result(self):
        """Create a mock zerox result with pages."""
        page1 = Mock()
        page1.content = "This is page 1 content"

        page2 = Mock()
        page2.content = "This is page 2 content"

        result = Mock()
        result.pages = [page1, page2]
        return result

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_success(
        self, mock_zerox, temp_input_file, temp_output_file, mock_zerox_result
    ):
        """Test successful transformation."""
        # Setup mock
        mock_zerox.side_effect = create_async_mock(mock_zerox_result)

        transformer = ZeroxTransformer(model="gpt-4o")
        result_path = transformer.transform(temp_input_file, temp_output_file)

        # Verify result
        assert result_path == temp_output_file
        assert temp_output_file.exists()

        # Verify content was written correctly
        content = temp_output_file.read_text()
        assert "This is page 1 content" in content
        assert "This is page 2 content" in content

        # Verify zerox was called with correct parameters
        mock_zerox.assert_called_once()
        call_args = mock_zerox.call_args
        assert str(temp_input_file) in str(call_args)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_with_custom_model(
        self, mock_zerox, temp_input_file, temp_output_file, mock_zerox_result
    ):
        """Test transformation with custom model."""
        mock_zerox.side_effect = create_async_mock(mock_zerox_result)

        transformer = ZeroxTransformer(model="gpt-4o-mini")
        transformer.transform(temp_input_file, temp_output_file)

        # Verify model was passed to zerox
        call_args = mock_zerox.call_args
        assert call_args.kwargs.get("model") == "gpt-4o-mini"

    def test_transform_input_file_not_found(self, tmp_path, temp_output_file):
        """Test transformation with non-existent input file."""
        non_existent = tmp_path / "does_not_exist.pdf"
        transformer = ZeroxTransformer()

        with pytest.raises(FileNotFoundError, match="Input file not found"):
            transformer.transform(non_existent, temp_output_file)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_timeout_error(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation timeout handling."""

        # Setup mock to raise TimeoutError
        async def timeout_coro(*args, **kwargs):
            await asyncio.sleep(1)
            raise TimeoutError("Operation timed out")

        mock_zerox.side_effect = timeout_coro

        transformer = ZeroxTransformer()

        with pytest.raises(RuntimeError, match="timed out after .* seconds"):
            transformer.transform(temp_input_file, temp_output_file)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_zerox_exception(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation with zerox exception."""
        # Setup mock to raise exception
        mock_zerox.side_effect = Exception("Zerox processing failed")

        transformer = ZeroxTransformer()

        with pytest.raises(RuntimeError, match="Failed to extract content from PDF"):
            transformer.transform(temp_input_file, temp_output_file)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_poppler_error(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation with Poppler-related error."""
        mock_zerox.side_effect = Exception("pdf2image requires Poppler")

        transformer = ZeroxTransformer()

        with pytest.raises(RuntimeError) as exc_info:
            transformer.transform(temp_input_file, temp_output_file)

        assert "Check that Poppler is installed" in str(exc_info.value)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_none_result(self, mock_zerox, temp_input_file, temp_output_file):
        """Test transformation when zerox returns None."""
        mock_zerox.side_effect = create_async_mock(None)

        transformer = ZeroxTransformer()

        with pytest.raises(RuntimeError, match="Zerox returned no pages"):
            transformer.transform(temp_input_file, temp_output_file)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_result_without_pages(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation when result has no pages attribute."""
        result = Mock(spec=[])  # Mock without 'pages' attribute
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()

        with pytest.raises(RuntimeError, match="Zerox returned no pages"):
            transformer.transform(temp_input_file, temp_output_file)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_result_with_none_pages(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation when result.pages is None."""
        result = Mock()
        result.pages = None
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()

        with pytest.raises(RuntimeError, match="Zerox returned no pages"):
            transformer.transform(temp_input_file, temp_output_file)

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_empty_pages(self, mock_zerox, temp_input_file, temp_output_file):
        """Test transformation with empty pages list."""
        result = Mock()
        result.pages = []
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()
        result_path = transformer.transform(temp_input_file, temp_output_file)

        # Should succeed but create empty output
        assert result_path == temp_output_file
        assert temp_output_file.exists()
        assert temp_output_file.read_text() == ""

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_pages_without_content(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation with pages that have no content."""
        page1 = Mock()
        page1.content = None

        page2 = Mock(spec=[])  # Mock without 'content' attribute

        result = Mock()
        result.pages = [page1, page2]
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()
        result_path = transformer.transform(temp_input_file, temp_output_file)

        # Should succeed but skip pages without content
        assert result_path == temp_output_file
        assert temp_output_file.exists()
        assert temp_output_file.read_text() == ""

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_mixed_pages(self, mock_zerox, temp_input_file, temp_output_file):
        """Test transformation with mix of pages with and without content."""
        page1 = Mock()
        page1.content = "Page 1 has content"

        page2 = Mock()
        page2.content = None

        page3 = Mock()
        page3.content = "Page 3 has content"

        result = Mock()
        result.pages = [page1, page2, page3]
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()
        result_path = transformer.transform(temp_input_file, temp_output_file)

        # Should only write pages with content
        assert result_path == temp_output_file
        content = temp_output_file.read_text()
        assert "Page 1 has content" in content
        assert "Page 3 has content" in content

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_content_formatting(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test that pages are separated by double newlines."""
        page1 = Mock()
        page1.content = "First page"

        page2 = Mock()
        page2.content = "Second page"

        page3 = Mock()
        page3.content = "Third page"

        result = Mock()
        result.pages = [page1, page2, page3]
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()
        transformer.transform(temp_input_file, temp_output_file)

        content = temp_output_file.read_text()
        # Each page should be followed by \n\n
        assert "First page\n\n" in content
        assert "Second page\n\n" in content
        assert "Third page\n\n" in content

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_unicode_content(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation with unicode content."""
        page1 = Mock()
        page1.content = "Hello 世界 🌍 café"

        result = Mock()
        result.pages = [page1]
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()
        transformer.transform(temp_input_file, temp_output_file)

        content = temp_output_file.read_text(encoding="utf-8")
        assert "Hello 世界 🌍 café" in content

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_multiline_content(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation with multiline page content."""
        page1 = Mock()
        page1.content = "Line 1\nLine 2\nLine 3"

        page2 = Mock()
        page2.content = "Another\nMultiline\nContent"

        result = Mock()
        result.pages = [page1, page2]
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()
        transformer.transform(temp_input_file, temp_output_file)

        content = temp_output_file.read_text()
        assert "Line 1\nLine 2\nLine 3" in content
        assert "Another\nMultiline\nContent" in content

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_large_document(
        self, mock_zerox, temp_input_file, temp_output_file
    ):
        """Test transformation with many pages."""
        # Create 100 pages
        pages = []
        for i in range(100):
            page = Mock()
            page.content = f"Page {i} content"
            pages.append(page)

        result = Mock()
        result.pages = pages
        mock_zerox.side_effect = create_async_mock(result)

        transformer = ZeroxTransformer()
        result_path = transformer.transform(temp_input_file, temp_output_file)

        assert result_path == temp_output_file
        content = temp_output_file.read_text()

        # Verify all pages were written
        for i in range(100):
            assert f"Page {i} content" in content

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_output_file_overwrite(
        self, mock_zerox, temp_input_file, temp_output_file, mock_zerox_result
    ):
        """Test that output file is overwritten if it exists."""
        # Create existing output file with content
        temp_output_file.write_text("Old content")

        mock_zerox.side_effect = create_async_mock(mock_zerox_result)

        transformer = ZeroxTransformer()
        transformer.transform(temp_input_file, temp_output_file)

        content = temp_output_file.read_text()
        assert "Old content" not in content
        assert "This is page 1 content" in content

    def test_transform_is_instance_of_transformer(self):
        """Test that ZeroxTransformer implements Transformer interface."""

        transformer = ZeroxTransformer()
        assert isinstance(transformer, Transformer)
        assert hasattr(transformer, "transform")
        assert callable(transformer.transform)


class TestZeroxTransformerIntegration:
    """Integration-style tests (still mocked but testing flow)."""

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_full_transformation_flow(self, mock_zerox, tmp_path):
        """Test complete transformation flow from input to output."""
        # Setup
        input_file = tmp_path / "document.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "output.txt"

        # Mock zerox result
        page1 = Mock()
        page1.content = "Chapter 1: Introduction"
        page2 = Mock()
        page2.content = "Chapter 2: Methods"
        page3 = Mock()
        page3.content = "Chapter 3: Results"

        result = Mock()
        result.pages = [page1, page2, page3]
        mock_zerox.side_effect = create_async_mock(result)

        # Execute
        transformer = ZeroxTransformer(model="gpt-4o")
        result_path = transformer.transform(input_file, output_file)

        # Verify
        assert result_path == output_file
        assert output_file.exists()

        content = output_file.read_text()
        assert "Chapter 1: Introduction" in content
        assert "Chapter 2: Methods" in content
        assert "Chapter 3: Results" in content

        # Verify proper formatting
        lines = content.split("\n")
        assert len([line for line in lines if line.strip()]) == 3  # 3 chapters

    @patch("app.services.doctransform.zerox_transformer.zerox")
    def test_transform_respects_timeout(self, mock_zerox, tmp_path):
        """Test that transformation respects the 10-minute timeout."""
        input_file = tmp_path / "document.pdf"
        input_file.write_bytes(b"PDF content")
        output_file = tmp_path / "output.txt"

        # Mock a long-running operation
        async def slow_operation(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate work
            result = Mock()
            result.pages = []
            return result

        mock_zerox.side_effect = slow_operation

        transformer = ZeroxTransformer()

        # Should complete within timeout
        result_path = transformer.transform(input_file, output_file)
        assert result_path == output_file
