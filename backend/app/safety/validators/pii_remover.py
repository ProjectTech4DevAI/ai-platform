from __future__ import annotations
import os
from guardrails import OnFailAction
from guardrails.validators import (
    FailResult,
    PassResult,
    register_validator,
    ValidationResult,
    Validator,
)
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from typing import Callable, ClassVar, List, Literal, Optional

from app.safety.utils.language_detector import LanguageDetector
from app.safety.validators.base_validator_config import BaseValidatorConfig

ALL_SUPPORTED_LANGUAGES = ["en", "hi"]

@register_validator(name="pii-remover", data_type="string")
class PIIRemover(Validator):
    """
    Anonymize sensitive data in the text using NLP (English only) and predefined regex patterns.
    Anonymizes detected entities with placeholders like [REDACTED_PERSON_1] and stores the real values in a Vault.
    Deanonymizer can be used to replace the placeholders back to their original values.
    """

    def __init__(
        self,
        entity_types=None,
        threshold=0.5,
        language="en",
        language_detector=None,
        on_fail: Optional[Callable] = OnFailAction.FIX
    ):
        super().__init__(on_fail=on_fail)

        self.entity_types = entity_types or ["ALL"]
        self.threshold = threshold
        self.language = language
        self.language_detector = language_detector or LanguageDetector()

        if self.language not in ALL_SUPPORTED_LANGUAGES:
            raise Exception(
                f"Language must be in {ALL_SUPPORTED_LANGUAGES}"
            )

        os.environ["TOKENIZERS_PARALLELISM"] = "false" # Disables huggingface/tokenizers warning

        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def _validate(self, value: str, metadata: dict = None) -> ValidationResult:
        text = value
        lang = self.language_detector.predict(text)

        if lang == self.language_detector.is_hindi(text):
            anonymized_text = self.run_hinglish_presidio(text)
        else:
            anonymized_text = self.run_english_presidio(text)

        if anonymized_text != text:
            return FailResult(
                error_message="PII detected and removed from the text.",
                fix_value=anonymized_text
            )
        return PassResult(value=text)        

    def run_english_presidio(self, text: str):
        results = self.analyzer.analyze(text=text,
                                language="en")
        anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text

    def run_hinglish_presidio(self, text: str):
        return text
    
class PIIRemoverSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["pii_remover"]
    entity_types: Optional[List[str]] = None
    threshold: float = 0.5
    language: str = "en"
    language_detector: Optional[LanguageDetector] = None
    validator_cls: ClassVar = PIIRemover