"""
Tests for evaluation_langfuse CRUD operations.
"""

from unittest.mock import MagicMock

import pytest

from app.crud.evaluation_langfuse import (
    create_langfuse_dataset_run,
    update_traces_with_cosine_scores,
    upload_dataset_to_langfuse_from_csv,
)


class TestCreateLangfuseDatasetRun:
    """Test creating Langfuse dataset runs."""

    def test_create_langfuse_dataset_run_success(self):
        """Test successfully creating a dataset run with traces."""
        # Mock Langfuse client
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()

        # Mock dataset items
        mock_item1 = MagicMock()
        mock_item1.id = "item_1"
        mock_item1.observe.return_value.__enter__.return_value = "trace_id_1"

        mock_item2 = MagicMock()
        mock_item2.id = "item_2"
        mock_item2.observe.return_value.__enter__.return_value = "trace_id_2"

        mock_dataset.items = [mock_item1, mock_item2]
        mock_langfuse.get_dataset.return_value = mock_dataset

        # Test data
        results = [
            {
                "item_id": "item_1",
                "question": "What is 2+2?",
                "generated_output": "4",
                "ground_truth": "4",
            },
            {
                "item_id": "item_2",
                "question": "What is the capital of France?",
                "generated_output": "Paris",
                "ground_truth": "Paris",
            },
        ]

        # Call function
        trace_id_mapping = create_langfuse_dataset_run(
            langfuse=mock_langfuse,
            dataset_name="test_dataset",
            run_name="test_run",
            results=results,
        )

        # Verify results
        assert len(trace_id_mapping) == 2
        assert trace_id_mapping["item_1"] == "trace_id_1"
        assert trace_id_mapping["item_2"] == "trace_id_2"

        # Verify Langfuse calls
        mock_langfuse.get_dataset.assert_called_once_with("test_dataset")
        mock_langfuse.flush.assert_called_once()
        assert mock_langfuse.trace.call_count == 2

    def test_create_langfuse_dataset_run_skips_missing_items(self):
        """Test that missing dataset items are skipped."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()

        # Only one item exists
        mock_item1 = MagicMock()
        mock_item1.id = "item_1"
        mock_item1.observe.return_value.__enter__.return_value = "trace_id_1"

        mock_dataset.items = [mock_item1]
        mock_langfuse.get_dataset.return_value = mock_dataset

        # Results include an item that doesn't exist in dataset
        results = [
            {
                "item_id": "item_1",
                "question": "What is 2+2?",
                "generated_output": "4",
                "ground_truth": "4",
            },
            {
                "item_id": "item_nonexistent",
                "question": "Invalid question",
                "generated_output": "Invalid",
                "ground_truth": "Invalid",
            },
        ]

        trace_id_mapping = create_langfuse_dataset_run(
            langfuse=mock_langfuse,
            dataset_name="test_dataset",
            run_name="test_run",
            results=results,
        )

        # Only the valid item should be in the mapping
        assert len(trace_id_mapping) == 1
        assert "item_1" in trace_id_mapping
        assert "item_nonexistent" not in trace_id_mapping

    def test_create_langfuse_dataset_run_handles_trace_error(self):
        """Test that trace creation errors are handled gracefully."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()

        # First item succeeds
        mock_item1 = MagicMock()
        mock_item1.id = "item_1"
        mock_item1.observe.return_value.__enter__.return_value = "trace_id_1"

        # Second item fails
        mock_item2 = MagicMock()
        mock_item2.id = "item_2"
        mock_item2.observe.side_effect = Exception("Trace creation failed")

        mock_dataset.items = [mock_item1, mock_item2]
        mock_langfuse.get_dataset.return_value = mock_dataset

        results = [
            {
                "item_id": "item_1",
                "question": "What is 2+2?",
                "generated_output": "4",
                "ground_truth": "4",
            },
            {
                "item_id": "item_2",
                "question": "What is the capital?",
                "generated_output": "Paris",
                "ground_truth": "Paris",
            },
        ]

        trace_id_mapping = create_langfuse_dataset_run(
            langfuse=mock_langfuse,
            dataset_name="test_dataset",
            run_name="test_run",
            results=results,
        )

        # Only successful item should be in mapping
        assert len(trace_id_mapping) == 1
        assert "item_1" in trace_id_mapping
        assert "item_2" not in trace_id_mapping

    def test_create_langfuse_dataset_run_empty_results(self):
        """Test with empty results list."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.items = []
        mock_langfuse.get_dataset.return_value = mock_dataset

        trace_id_mapping = create_langfuse_dataset_run(
            langfuse=mock_langfuse,
            dataset_name="test_dataset",
            run_name="test_run",
            results=[],
        )

        assert len(trace_id_mapping) == 0
        mock_langfuse.flush.assert_called_once()


class TestUpdateTracesWithCosineScores:
    """Test updating Langfuse traces with cosine similarity scores."""

    def test_update_traces_with_cosine_scores_success(self):
        """Test successfully updating traces with scores."""
        mock_langfuse = MagicMock()

        per_item_scores = [
            {"trace_id": "trace_1", "cosine_similarity": 0.95},
            {"trace_id": "trace_2", "cosine_similarity": 0.87},
            {"trace_id": "trace_3", "cosine_similarity": 0.92},
        ]

        update_traces_with_cosine_scores(
            langfuse=mock_langfuse, per_item_scores=per_item_scores
        )

        # Verify score was called for each item
        assert mock_langfuse.score.call_count == 3

        # Verify the score calls
        calls = mock_langfuse.score.call_args_list
        assert calls[0].kwargs["trace_id"] == "trace_1"
        assert calls[0].kwargs["name"] == "cosine_similarity"
        assert calls[0].kwargs["value"] == 0.95
        assert "cosine similarity" in calls[0].kwargs["comment"].lower()

        assert calls[1].kwargs["trace_id"] == "trace_2"
        assert calls[1].kwargs["value"] == 0.87

        mock_langfuse.flush.assert_called_once()

    def test_update_traces_with_cosine_scores_missing_trace_id(self):
        """Test that items without trace_id are skipped."""
        mock_langfuse = MagicMock()

        per_item_scores = [
            {"trace_id": "trace_1", "cosine_similarity": 0.95},
            {"cosine_similarity": 0.87},  # Missing trace_id
            {"trace_id": "trace_3", "cosine_similarity": 0.92},
        ]

        update_traces_with_cosine_scores(
            langfuse=mock_langfuse, per_item_scores=per_item_scores
        )

        # Should only call score for items with trace_id
        assert mock_langfuse.score.call_count == 2

    def test_update_traces_with_cosine_scores_error_handling(self):
        """Test that score errors don't stop processing."""
        mock_langfuse = MagicMock()

        # First call succeeds, second fails, third succeeds
        mock_langfuse.score.side_effect = [None, Exception("Score failed"), None]

        per_item_scores = [
            {"trace_id": "trace_1", "cosine_similarity": 0.95},
            {"trace_id": "trace_2", "cosine_similarity": 0.87},
            {"trace_id": "trace_3", "cosine_similarity": 0.92},
        ]

        # Should not raise exception
        update_traces_with_cosine_scores(
            langfuse=mock_langfuse, per_item_scores=per_item_scores
        )

        # All three should have been attempted
        assert mock_langfuse.score.call_count == 3
        mock_langfuse.flush.assert_called_once()

    def test_update_traces_with_cosine_scores_empty_list(self):
        """Test with empty scores list."""
        mock_langfuse = MagicMock()

        update_traces_with_cosine_scores(langfuse=mock_langfuse, per_item_scores=[])

        mock_langfuse.score.assert_not_called()
        mock_langfuse.flush.assert_called_once()


class TestUploadDatasetToLangfuseFromCsv:
    """Test uploading datasets to Langfuse from CSV content."""

    @pytest.fixture
    def valid_csv_content(self):
        """Valid CSV content."""
        csv_string = """question,answer
"What is 2+2?","4"
"What is the capital of France?","Paris"
"Who wrote Romeo and Juliet?","Shakespeare"
"""
        return csv_string.encode("utf-8")

    def test_upload_dataset_to_langfuse_from_csv_success(self, valid_csv_content):
        """Test successful upload with duplication."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "dataset_123"
        mock_langfuse.create_dataset.return_value = mock_dataset

        langfuse_id, total_items = upload_dataset_to_langfuse_from_csv(
            langfuse=mock_langfuse,
            csv_content=valid_csv_content,
            dataset_name="test_dataset",
            duplication_factor=5,
        )

        assert langfuse_id == "dataset_123"
        assert total_items == 15  # 3 items * 5 duplication

        # Verify dataset creation
        mock_langfuse.create_dataset.assert_called_once_with(name="test_dataset")

        # Verify dataset items were created (3 original * 5 duplicates = 15)
        assert mock_langfuse.create_dataset_item.call_count == 15

        mock_langfuse.flush.assert_called_once()

    def test_upload_dataset_to_langfuse_from_csv_duplication_metadata(
        self, valid_csv_content
    ):
        """Test that duplication metadata is included."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "dataset_123"
        mock_langfuse.create_dataset.return_value = mock_dataset

        upload_dataset_to_langfuse_from_csv(
            langfuse=mock_langfuse,
            csv_content=valid_csv_content,
            dataset_name="test_dataset",
            duplication_factor=3,
        )

        # Check metadata in create_dataset_item calls
        calls = mock_langfuse.create_dataset_item.call_args_list

        # Each original item should have 3 duplicates
        duplicate_numbers = []
        for call_args in calls:
            metadata = call_args.kwargs.get("metadata", {})
            duplicate_numbers.append(metadata.get("duplicate_number"))
            assert metadata.get("duplication_factor") == 3

        # Should have 3 sets of duplicates (1, 2, 3)
        assert duplicate_numbers.count(1) == 3  # 3 original items, each with dup #1
        assert duplicate_numbers.count(2) == 3  # 3 original items, each with dup #2
        assert duplicate_numbers.count(3) == 3  # 3 original items, each with dup #3

    def test_upload_dataset_to_langfuse_from_csv_missing_columns(self):
        """Test with CSV missing required columns."""
        mock_langfuse = MagicMock()

        invalid_csv = b"query,response\nWhat is 2+2?,4\n"

        with pytest.raises(ValueError, match="question.*answer"):
            upload_dataset_to_langfuse_from_csv(
                langfuse=mock_langfuse,
                csv_content=invalid_csv,
                dataset_name="test_dataset",
                duplication_factor=1,
            )

    def test_upload_dataset_to_langfuse_from_csv_empty_rows(self):
        """Test that empty rows are skipped."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "dataset_123"
        mock_langfuse.create_dataset.return_value = mock_dataset

        # CSV with some empty rows
        csv_with_empty = b"""question,answer
"Valid question 1","Valid answer 1"
"","Empty answer"
"Valid question 2",""
"Valid question 3","Valid answer 3"
"""

        langfuse_id, total_items = upload_dataset_to_langfuse_from_csv(
            langfuse=mock_langfuse,
            csv_content=csv_with_empty,
            dataset_name="test_dataset",
            duplication_factor=2,
        )

        # Should only process 2 valid items (first and last)
        assert total_items == 4  # 2 valid items * 2 duplication
        assert mock_langfuse.create_dataset_item.call_count == 4

    def test_upload_dataset_to_langfuse_from_csv_empty_dataset(self):
        """Test with CSV that has no valid items."""
        mock_langfuse = MagicMock()

        empty_csv = b"""question,answer
"",""
"","answer without question"
"""

        with pytest.raises(ValueError, match="No valid items found"):
            upload_dataset_to_langfuse_from_csv(
                langfuse=mock_langfuse,
                csv_content=empty_csv,
                dataset_name="test_dataset",
                duplication_factor=1,
            )

    def test_upload_dataset_to_langfuse_from_csv_invalid_encoding(self):
        """Test with invalid CSV encoding."""
        mock_langfuse = MagicMock()

        # Invalid UTF-8 bytes
        invalid_csv = b"\xff\xfe Invalid UTF-8"

        with pytest.raises((ValueError, Exception)):
            upload_dataset_to_langfuse_from_csv(
                langfuse=mock_langfuse,
                csv_content=invalid_csv,
                dataset_name="test_dataset",
                duplication_factor=1,
            )

    def test_upload_dataset_to_langfuse_from_csv_default_duplication(
        self, valid_csv_content
    ):
        """Test upload with duplication factor of 1."""
        mock_langfuse = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "dataset_123"
        mock_langfuse.create_dataset.return_value = mock_dataset

        langfuse_id, total_items = upload_dataset_to_langfuse_from_csv(
            langfuse=mock_langfuse,
            csv_content=valid_csv_content,
            dataset_name="test_dataset",
            duplication_factor=1,
        )

        assert total_items == 3  # 3 items * 1 duplication
        assert mock_langfuse.create_dataset_item.call_count == 3
