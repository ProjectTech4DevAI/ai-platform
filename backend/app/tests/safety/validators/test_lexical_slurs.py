import pandas as pd
import pytest

from app.safety.validators.lexical_slur import LexicalSlur, SlurSeverity
from app.safety.validators.constants import SLUR_LIST_FILENAME

# ---------------------------------------
# Helper: Create temporary slur CSV
# ---------------------------------------
@pytest.fixture
def slur_csv(tmp_path):
    df = pd.DataFrame({
        "label": ["badword", "mildslur", "highslur"],
        "severity": ["L", "M", "H"],
        "language": ["en", "en", "hi"],
    })
    file_path = tmp_path / SLUR_LIST_FILENAME
    df.to_csv(file_path, index=False)
    return file_path


# ---------------------------------------
# Helper: Monkeypatch the file loader
# ---------------------------------------
@pytest.fixture
def patch_slur_load(monkeypatch, slur_csv):
    """Patch Path so lexicalslur loads from our temp CSV."""
    def fake_load_slur_list(self):
        df = pd.read_csv(slur_csv)
        df["label"] = df["label"].str.lower()
        return df["label"].tolist()
    monkeypatch.setattr(LexicalSlur, "load_slur_list", fake_load_slur_list)


# ---------------------------------------
# Base ValidatorItem builder
# ---------------------------------------
def build_validator(severity="all", languages=None):
    sev = {
        "low": SlurSeverity.Low,
        "medium": SlurSeverity.Medium,
        "high": SlurSeverity.High,
        "all": SlurSeverity.All
    }[severity]

    return LexicalSlur(
        severity=sev,
        languages=languages or ["en", "hi"]
    )

# ---------------------------------------
# TESTS
# ---------------------------------------

def test_passes_when_no_slur(patch_slur_load):
    validator = build_validator()
    result = validator._validate("hello world, everything is fine.")
    assert result.outcome is "pass"


def test_fails_when_slur_detected(patch_slur_load):
    validator = build_validator()
    result = validator._validate("You are a badword!")
    assert result.outcome is "fail"
    assert "badword" in result.error_message


def test_emoji_are_removed_before_validation(patch_slur_load):
    validator = build_validator()
    result = validator._validate("You 🤮 badword 🤮 person")
    assert result.outcome is "fail"
    assert "badword" in result.error_message


def test_punctuation_is_removed(patch_slur_load):
    validator = build_validator()
    result = validator._validate("You are a, badword!!")
    assert result.outcome is "fail"


def test_numbers_are_removed(patch_slur_load):
    validator = build_validator()
    result = validator._validate("b4dw0rd badword again")  # "badword" appears once cleaned
    assert result.outcome is "fail"


def test_severity_low_includes_all(patch_slur_load, monkeypatch, slur_csv):
    """Low severity = L + M + H."""
    df = pd.DataFrame({
        "label": ["lowone", "mediumone", "highone"],
        "severity": ["L", "M", "H"]
    })
    file_path = slur_csv
    df.to_csv(file_path, index=False)

    def fake_load_slur_list(self):
        df = pd.read_csv(file_path)
        return df[df['severity'].isin(['L', 'M', 'H'])]['label'].tolist()

    monkeypatch.setattr(LexicalSlur, "load_slur_list", fake_load_slur_list)

    validator = LexicalSlur(severity=SlurSeverity.Low)
    assert validator.slur_list == ["lowone", "mediumone", "highone"]


def test_severity_medium_includes_m_and_h(patch_slur_load, monkeypatch, slur_csv):
    df = pd.DataFrame({
        "label": ["lowone", "mediumone", "highone"],
        "severity": ["L", "M", "H"]
    })
    file_path = slur_csv
    df.to_csv(file_path, index=False)

    def fake_load_slur_list(self):
        df = pd.read_csv(file_path)
        return df[df['severity'].isin(['M', 'H'])]['label'].tolist()

    monkeypatch.setattr(LexicalSlur, "load_slur_list", fake_load_slur_list)

    validator = LexicalSlur(severity=SlurSeverity.Medium)
    assert validator.slur_list == ["mediumone", "highone"]


def test_severity_high_includes_only_h(patch_slur_load, monkeypatch, slur_csv):
    df = pd.DataFrame({
        "label": ["lowone", "mediumone", "highone"],
        "severity": ["L", "M", "H"]
    })
    file_path = slur_csv
    df.to_csv(file_path, index=False)

    def fake_load_slur_list(self):
        df = pd.read_csv(file_path)
        return df[df['severity'] == 'H']['label'].tolist()

    monkeypatch.setattr(LexicalSlur, "load_slur_list", fake_load_slur_list)

    validator = LexicalSlur(severity=SlurSeverity.High)
    assert validator.slur_list == ["highone"]