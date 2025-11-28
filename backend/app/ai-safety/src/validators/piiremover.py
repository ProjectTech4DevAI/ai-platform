from __future__ import annotations
import os
from guardrails.validators import (
    FailResult,
    PassResult,
    register_validator,
    ValidationResult,
    Validator,
)
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from typing import Callable, Optional

from ..utils.exception import LLMGuardValidationError
from ..utils.languagedetector import LanguageDetector
from ..utils.util import ValidatorItem

ALL_SUPPORTED_LANGUAGES = ["en", "hi"]

@register_validator(name="pii-remover", data_type="string")
class PIIRemover(Validator):
    """
    Anonymize sensitive data in the text using NLP (English only) and predefined regex patterns.

    Anonymizes detected entities with placeholders like [REDACTED_PERSON_1] and stores the real values in a Vault.
    Deanonymizer can be used to replace the placeholders back to their original values.
    """

    def __init__(self, validator_config: ValidatorItem, on_fail: Optional[Callable] = None):
        super().__init__(on_fail=on_fail)

        params = validator_config.params or {}
        self.entity_types = params.get("entity_types", ["ALL"])
        self.threshold = params.get("threshold", 0.5)
        self.language = params.get("language", "en")
        self.language_detector = params.get("language_detector", LanguageDetector())

        if self.language not in ALL_SUPPORTED_LANGUAGES:
            raise LLMGuardValidationError(
                f"Language must be in the list of allowed: {ALL_SUPPORTED_LANGUAGES}"
            )

        os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Disables huggingface/tokenizers warning

        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def _validate(self, text: str) -> ValidationResult:
        lang = self.language_detector.predict(text)

        if lang == self.language_detector.is_hindi(text):
            anonymized_text = self.run_hinglish_presidio(text)
        else:
            anonymized_text = self.run_english_presidio(text)

        if anonymized_text != text:
            return FailResult(
                error_message=f"{text} failed validation. Detected PII data and anonymized to {anonymized_text}."
            )
        return PassResult(value=text)        

    def run_english_presidio(self, text: str):
        results = self.analyzer.analyze(text=text,
                                language="en")
        anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text

    def run_hinglish_presidio(self, text: str):
        return text