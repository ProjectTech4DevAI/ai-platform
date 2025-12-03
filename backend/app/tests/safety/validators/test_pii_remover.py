import pytest
from unittest.mock import MagicMock, patch

from app.safety.validators.pii_remover import PIIRemover, ALL_SUPPORTED_LANGUAGES

# -------------------------------
# Basic fixture with mock Presidio
# -------------------------------
@pytest.fixture
def mock_presidio():
    """Mock AnalyzerEngine and AnonymizerEngine before validator loads."""
    with patch("app.safety.validators.pii_remover.AnalyzerEngine") as mock_analyzer, \
         patch("app.safety.validators.pii_remover.AnonymizerEngine") as mock_anonymizer:

        mock_analyzer.return_value.analyze.return_value = []
        mock_anonymizer.return_value.anonymize.return_value = MagicMock(
            text="redacted text"
        )
        yield mock_analyzer, mock_anonymizer

@pytest.fixture
def validator(mock_presidio):
    """
    A validator with simple config.
    """
    return PIIRemover(
        entity_types=None,
        threshold=0.5,
        language="en",
        language_detector=MagicMock(),  # mock so predict/is_hindi can be controlled
    )

# -------------------------
# TESTS BEGIN
# -------------------------

def test_validator_initialization(validator):
    assert validator.language in ALL_SUPPORTED_LANGUAGES
    assert isinstance(validator.entity_types, list)
    assert len(validator.entity_types) > 0


def test_validate_pass_result_when_presidio_returns_string(validator):
    # Mock analyzer/anonymizer pipeline
    with patch.object(validator, "run_english_presidio", return_value="no pii here"):
        result = validator._validate("no pii here")
        assert result.outcome is "pass"

def test_validate_pass_result_when_presidio_returns_engine_result(validator):
    mock_engine = MagicMock()
    mock_engine.text = "redacted text"

    with patch.object(validator, "run_english_presidio", return_value=mock_engine):
        result = validator._validate("hello world")
        assert result.outcome is "fail"

def test_fail_if_anonymized_is_none(validator):
    with patch.object(validator, "run_english_presidio", return_value=None):
        result = validator._validate("something")
        assert result.outcome is "fail"

def test_english_path_called_when_language_not_hindi(validator):
    with patch.object(validator.language_detector, "predict", return_value="en"):
        with patch.object(validator.language_detector, "is_hindi", return_value="hi"):
            with patch.object(validator, "run_english_presidio") as mock_eng:
                validator._validate("text")
                mock_eng.assert_called_once()

def test_hinglish_path_called_for_hindi_text(validator):
    with patch.object(validator.language_detector, "predict", return_value="hi"):
        with patch.object(validator.language_detector, "is_hindi", return_value="hi"):
            with patch.object(validator, "run_hinglish_presidio") as mock_hing:
                validator._validate("text")
                mock_hing.assert_called_once()

def test_default_entity_types_applied(validator):
    # entity types should be filtered to builtins; analyzer mocked so entity_types remains list
    assert isinstance(validator.entity_types, list)
    assert len(validator.entity_types) > 0


def test_custom_entity_types_override(mock_presidio):
    v = PIIRemover(
        entity_types=["EMAIL_ADDRESS"],
        threshold=0.5,
        language="en",
        language_detector=MagicMock(),
    )
    assert v.entity_types == ["EMAIL_ADDRESS"]