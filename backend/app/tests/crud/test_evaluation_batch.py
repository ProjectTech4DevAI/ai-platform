"""Tests for evaluation batch output parsing."""

import json
from app.crud.evaluation_batch import parse_batch_output


def test_parse_batch_output_complex_structure():
    """Test parsing batch output with complex answer structure."""
    # Batch output JSONL with complex structure
    jsonl_content = json.dumps(
        {
            "custom_id": "item_123",
            "response": {
                "status_code": 200,
                "body": {
                    "id": "resp_abc",
                    "output": [
                        {
                            "type": "file_search_call",
                            "status": "completed",
                        },
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "This is the extracted answer.",
                                }
                            ],
                        },
                    ],
                },
            },
        }
    )

    # Dataset items
    dataset_items = [
        {
            "id": "item_123",
            "input": {"question": "What is the answer?"},
            "expected_output": {"answer": "Expected answer"},
        }
    ]

    results = parse_batch_output(jsonl_content, dataset_items)

    assert len(results) == 1
    assert results[0]["item_id"] == "item_123"
    assert results[0]["question"] == "What is the answer?"
    assert results[0]["generated_output"] == "This is the extracted answer."
    assert results[0]["ground_truth"] == "Expected answer"


def test_parse_batch_output_simple_string():
    """Test parsing batch output with simple string output."""
    # Batch output JSONL with simple string
    jsonl_content = json.dumps(
        {
            "custom_id": "item_456",
            "response": {
                "status_code": 200,
                "body": {
                    "id": "resp_def",
                    "output": "Simple string answer",
                },
            },
        }
    )

    # Dataset items
    dataset_items = [
        {
            "id": "item_456",
            "input": {"question": "Simple question?"},
            "expected_output": {"answer": "Simple expected"},
        }
    ]

    results = parse_batch_output(jsonl_content, dataset_items)

    assert len(results) == 1
    assert results[0]["item_id"] == "item_456"
    assert results[0]["generated_output"] == "Simple string answer"


def test_parse_batch_output_error_handling():
    """Test parsing batch output with error response."""
    # Batch output JSONL with error
    jsonl_content = json.dumps(
        {
            "custom_id": "item_789",
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
            },
        }
    )

    # Dataset items
    dataset_items = [
        {
            "id": "item_789",
            "input": {"question": "Error question?"},
            "expected_output": {"answer": "Error expected"},
        }
    ]

    results = parse_batch_output(jsonl_content, dataset_items)

    assert len(results) == 1
    assert results[0]["item_id"] == "item_789"
    assert "ERROR: Rate limit exceeded" in results[0]["generated_output"]


def test_parse_batch_output_stringified_list():
    """Test parsing batch output with stringified Python list (single quotes)."""
    # This is the exact format you showed - Python string representation of a list
    stringified_output = str(
        [
            {
                "id": "fs_0a09867e650850280068ee8d506cd081959c3e4891a733e591",
                "type": "file_search_call",
                "status": "completed",
                "queries": [
                    "सीएलएफ की आरजीबी बैठक में आय और व्यय का विवरण प्रस्तुत करने के लिए कौन जिम्मेदार है?"
                ],
                "results": None,
            },
            {
                "id": "msg_0a09867e650850280068ee8d515d5881959de222d6218b4804",
                "type": "message",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "logprobs": [],
                        "text": "I'm sorry, I couldn't find any relevant information regarding who is responsible for presenting the income and expenditure details at the RGB meeting of CLF in the provided file. If there is more data or another file, I can check that for you.",
                    }
                ],
                "role": "assistant",
            },
        ]
    )

    # Batch output JSONL with stringified list
    jsonl_content = json.dumps(
        {
            "custom_id": "item_stringified",
            "response": {
                "status_code": 200,
                "body": {
                    "id": "resp_str",
                    "output": stringified_output,
                },
            },
        }
    )

    # Dataset items
    dataset_items = [
        {
            "id": "item_stringified",
            "input": {"question": "Stringified question?"},
            "expected_output": {"answer": "Stringified expected"},
        }
    ]

    results = parse_batch_output(jsonl_content, dataset_items)

    assert len(results) == 1
    assert results[0]["item_id"] == "item_stringified"
    assert (
        results[0]["generated_output"]
        == "I'm sorry, I couldn't find any relevant information regarding who is responsible for presenting the income and expenditure details at the RGB meeting of CLF in the provided file. If there is more data or another file, I can check that for you."
    )
