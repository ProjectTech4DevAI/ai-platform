from enum import Enum
from guardrails import OnFailAction
from guardrails.validators import (
    FailResult,
    PassResult,
    register_validator,
    ValidationResult,
    Validator
)
from pathlib import Path
from typing import Callable, ClassVar, List, Literal, Optional, Union, Annotated

import emoji
import ftfy
import pandas
import re
import string
import unicodedata

from app.safety.validators.constants import SLUR_LIST_FILENAME
from app.safety.validators.base_validator_config import BaseValidatorConfig

class SlurSeverity(Enum):
    Low = "low"
    Medium = "medium"
    High = "high"
    All = "all"

@register_validator(name="lexical-slur", data_type="string")
class LexicalSlur(Validator):
    """
    Validate text for the presence of lexical slurs using a predefined list.
    """

    def __init__(
        self, 
        severity: SlurSeverity = SlurSeverity.All,
        languages: Optional[list] = None,
        on_fail: Optional[Callable] = OnFailAction.FIX
    ):    
        """
        Initialize the LexicalSlur validator with severity, language scope, and failure handling.
        
        Parameters:
            severity (SlurSeverity): Which severity levels of slurs to consider when detecting content.
            languages (Optional[list]): List of language codes to restrict detection to; defaults to ["en", "hi"] if omitted.
            on_fail (Optional[Callable]): Action to perform when validation fails (e.g., fix, warn); defaults to OnFailAction.FIX.
        
        Description:
            Loads the slur list according to `severity` and prepares the validator to search input text for those slurs.
        """
        self.severity = severity
        self.languages = languages or ["en", "hi"]
        self.slur_list = self.load_slur_list()
        self.text = None
        super().__init__(on_fail=on_fail, search_words=self.slur_list)

    def _validate(self, value: str, metadata: dict = None) -> ValidationResult:
        """
        Detects lexical slurs in the input string (exact word matches after normalization and cleaning) and returns a failure with a redacted fix when any are found.
        
        The input is normalized by removing emojis, digits, punctuation, and by lowercasing and collapsing whitespace before tokenizing on spaces. Each slur present as an exact token from the validator's loaded slur list is collected; if any are detected they are replaced with "[REDACTED_SLUR]" in the returned fix value.
        
        Parameters:
            value (str): The input text to validate.
            metadata (dict, optional): Additional metadata for the validation call (not used by this validator).
        
        Returns:
            ValidationResult: A FailResult containing an `error_message` listing detected slurs and a `fix_value` with those slurs redacted if any were found; otherwise a PassResult with the cleaned text.
        """
        self.text = value
        self.text = self.remove_emojis(self.text)
        self.text = self.remove_nos(self.text)
        self.text = self.clean_text(self.text)
        words = self.text.split()
        detected_slurs = []

        for slur in self.slur_list:
            if slur in words:
                if slur not in detected_slurs:
                    detected_slurs.append(slur)

        if len(detected_slurs) > 0:
            for word in words:
                if word in detected_slurs:
                    self.text = self.text.replace(word, "[REDACTED_SLUR]")

        if len(detected_slurs) > 0:
            return FailResult(
                error_message=f"Mentioned toxic words: {', '.join(detected_slurs)}",
                fix_value=self.text
            )

        return PassResult(value=self.text)

    def normalize_text(self, text):
        # Fix mojibake, weird encodings, etc.
        """
        Normalize text by fixing encoding issues and applying Unicode NFKC normalization.
        
        Parameters:
            text (str): Input text to normalize.
        
        Returns:
            str: Text with mojibake and odd encodings corrected and characters normalized to Unicode NFKC form.
        """
        text = ftfy.fix_text(text)
        # Normalize to NFKC form — converts fancy fonts to plain
        text = unicodedata.normalize("NFKC", text)
        return text

    def remove_emojis(self, text):
        """
        Remove all emoji characters from the given text.
        
        Parameters:
            text (str): Input string that may contain emoji characters.
        
        Returns:
            str: The input string with all emoji characters removed.
        """
        return emoji.replace_emoji(text, replace='')

    def clean_text(self, text):
        """
        Return a cleaned version of the input text suitable for lexical matching.
        
        Parameters:
            text (str): Input text to clean.
        
        Returns:
            str: Text with punctuation removed, converted to lowercase, consecutive whitespace collapsed to single spaces, and leading/trailing whitespace trimmed.
        """
        text = self.normalize_text(text)
        translator = str.maketrans('', '', string.punctuation)
        clean_text = text.translate(translator).lower()
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text

    def remove_nos(self, text):
        """
        Remove all numeric digits from the input text.
        
        Parameters:
            text (str): Input string potentially containing digits.
        
        Returns:
            str: The input string with all digit characters removed.
        """
        text = re.sub(r'\d+', '', text)
        return text

    def load_slur_list(self):
        """
        Load the slur list CSV and return normalized slur labels filtered by the configured severity.
        
        Reads the CSV file named by SLUR_LIST_FILENAME located in validators/lexical_slur under the project base directory (two levels up from this file), lowercases the `label` column, and returns a list of slur labels filtered according to `self.severity`:
        - SlurSeverity.Low: include severities 'L', 'M', 'H'
        - SlurSeverity.Medium: include severities 'M', 'H'
        - SlurSeverity.High: include severity 'H'
        - SlurSeverity.All: include all labels
        
        Returns:
            list[str]: Lowercased slur labels matching the configured severity.
        """
        BASE_DIR = Path(__file__).resolve().parent.parent  # goes up from validators/ to src/
        file_path = f"{BASE_DIR}/validators/lexical_slur/{SLUR_LIST_FILENAME}"

        df = pandas.read_csv(file_path)
        df['label'] = df['label'].str.lower()

        # TODO - filter by languages if specified

        if self.severity == SlurSeverity.Low:
            return df[df['severity'].isin(['L', 'M', 'H'])]['label'].tolist()
        elif self.severity == SlurSeverity.Medium:
            return df[df['severity'].isin(['M', 'H'])]['label'].tolist()
        elif self.severity == SlurSeverity.High:
            return df[df['severity'] == 'H']['label'].tolist()

        return df['label'].tolist()

    
class LexicalSlurSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["uli_slur_match"]
    languages: List[str] = ["en", "hi"]
    severity: Literal["low", "medium", "high", "all"] = "all"
    validator_cls: ClassVar = LexicalSlur