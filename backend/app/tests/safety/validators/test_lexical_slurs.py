import pandas as pd
import pytest

from app.safety.validators.lexical_slur import LexicalSlur, SlurSeverity
from app.safety.validators.constants import SLUR_LIST_FILENAME

# ---------------------------------------
# Helper: Create temporary slur CSV
# ---------------------------------------
@pytest.fixture
def slur_csv(tmp_path):
    """
    Create a temporary CSV file containing example slur entries and return its path.
    
    The CSV contains columns: `label`, `severity`, and `language` with three sample rows:
    - "badword" (L, en)
    - "mildslur" (M, en)
    - "highslur" (H, hi)
    
    Returns:
        pathlib.Path: Path to the created CSV file named by SLUR_LIST_FILENAME within `tmp_path`.
    """
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
    """
    Patch LexicalSlur.load_slur_list so it loads slur labels from the provided temporary CSV.
    
    Parameters:
        slur_csv (str | pathlib.Path): Path to a CSV file containing a 'label' column; the patched loader will read this file and return the list of labels lowercased.
    """
    def fake_load_slur_list(self):
        """
        Load slur labels from the test CSV and return them lowercased.
        
        Reads the CSV file at the `slur_csv` path, converts the `label` column to lowercase, and returns the labels as a list.
        
        Returns:
            list[str]: Lowercase slur labels loaded from the CSV.
        """
        df = pd.read_csv(slur_csv)
        df["label"] = df["label"].str.lower()
        return df["label"].tolist()
    monkeypatch.setattr(LexicalSlur, "load_slur_list", fake_load_slur_list)


# ---------------------------------------
# Base ValidatorItem builder
# ---------------------------------------
def build_validator(severity="all", languages=None):
    """
    Create a LexicalSlur validator configured with the given severity level and languages.
    
    Parameters:
        severity (str): Severity level to include; one of "low", "medium", "high", or "all". Defaults to "all".
        languages (list[str] | None): List of language codes to enable for the validator. If omitted, defaults to ["en", "hi"].
    
    Returns:
        LexicalSlur: A LexicalSlur instance configured with the requested severity and languages.
    """
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
        """
        Load slur labels from the CSV at the surrounding scope and return those with severities 'L', 'M', or 'H'.
        
        Returns:
            list[str]: Labels from the CSV whose `severity` value is 'L', 'M', or 'H', in the CSV order.
        """
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
        """
        Load slur labels from the CSV located at `file_path`, returning only labels with severity 'M' (medium) or 'H' (high).
        
        Returns:
            slur_list (list): List of slur labels (strings) whose `severity` is 'M' or 'H'.
        """
        df = pd.read_csv(file_path)
        return df[df['severity'].isin(['M', 'H'])]['label'].tolist()

    monkeypatch.setattr(LexicalSlur, "load_slur_list", fake_load_slur_list)

    validator = LexicalSlur(severity=SlurSeverity.Medium)
    assert validator.slur_list == ["mediumone", "highone"]


def test_severity_high_includes_only_h(patch_slur_load, monkeypatch, slur_csv):
    """
    Verify that configuring the validator with High severity includes only slurs labeled 'H'.
    
    Creates a CSV containing labels with severities L, M, and H, patches LexicalSlur.load_slur_list to load only labels with severity 'H', constructs a LexicalSlur with SlurSeverity.High, and asserts its slur_list contains only "highone".
    """
    df = pd.DataFrame({
        "label": ["lowone", "mediumone", "highone"],
        "severity": ["L", "M", "H"]
    })
    file_path = slur_csv
    df.to_csv(file_path, index=False)

    def fake_load_slur_list(self):
        """
        Load slur labels marked with high severity from the CSV located at `file_path`.
        
        Reads the CSV file at the surrounding `file_path` variable and returns a list of values from the `label` column for rows where the `severity` column equals `'H'`.
        
        Returns:
            list: Slur labels with severity 'H'.
        """
        df = pd.read_csv(file_path)
        return df[df['severity'] == 'H']['label'].tolist()

    monkeypatch.setattr(LexicalSlur, "load_slur_list", fake_load_slur_list)

    validator = LexicalSlur(severity=SlurSeverity.High)
    assert validator.slur_list == ["highone"]