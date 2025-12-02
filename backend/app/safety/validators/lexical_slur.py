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
        self.severity = severity
        self.languages = languages or ["en", "hi"]
        self.slur_list = self.load_slur_list()
        self.text = None
        super().__init__(on_fail=on_fail, search_words=self.slur_list)

    def _validate(self, value: str, metadata: dict = None) -> ValidationResult:
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
        text = ftfy.fix_text(text)
        # Normalize to NFKC form — converts fancy fonts to plain
        text = unicodedata.normalize("NFKC", text)
        return text

    def remove_emojis(self, text):
        return emoji.replace_emoji(text, replace='')

    def clean_text(self, text):
        text = self.normalize_text(text)
        translator = str.maketrans('', '', string.punctuation)
        clean_text = text.translate(translator).lower()
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text

    def remove_nos(self, text):
        text = re.sub(r'\d+', '', text)
        return text

    def load_slur_list(self):
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