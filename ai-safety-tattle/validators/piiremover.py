from __future__ import annotations

import os
import re
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from ..utils.exception import LLMGuardValidationError
from ..utils.languagedetector import LanguageDetector
from ..validator import Validator

DEFAULT_ENTITY_TYPES = [
    "CREDIT_CARD",
    "CRYPTO",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "NRP",
    "PERSON",
    "PHONE_NUMBER",
    "IN_PAN",
    "IN_AADHAAR",
    "IN_VEHICLE_REGISTRATION",
    "IN_VOTER",
    "IN_PASSPORT",
    "IN_GSTIN",
]

ALL_SUPPORTED_LANGUAGES = ["en", "hi"]

class PIIRemover(Validator):
    """
    Anonymize sensitive data in the text using NLP (English only) and predefined regex patterns.

    Anonymizes detected entities with placeholders like [REDACTED_PERSON_1] and stores the real values in a Vault.
    Deanonymizer can be used to replace the placeholders back to their original values.
    """

    def __init__(
        self,
        entity_types: list[str] | None = None,
        threshold: float = 0.5,
        language: str = "en",
        language_detector: LanguageDetector | None = None,
    ) -> None:
        """
        Initialize an instance of Anonymize class.

        Parameters:
            entity_types: List of entity types to be detected. If not provided, defaults to all.
            threshold: Acceptance threshold. Default is 0.
            language: Language of the anonymize detect. Default is "en".
        """

        if language not in ALL_SUPPORTED_LANGUAGES:
            raise LLMGuardValidationError(
                f"Language must be in the list of allowed: {ALL_SUPPORTED_LANGUAGES}"
            )

        os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Disables huggingface/tokenizers warning

        if not entity_types:
            entity_types = DEFAULT_ENTITY_TYPES.copy()

        entity_types.append("CUSTOM")

        self._entity_types = entity_types
        self._threshold = threshold
        self._language = language
        self._language_detector = (
            language_detector if language_detector else LanguageDetector()
        )
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def execute(self, text: str):
        lang = self._language_detector.predict(text)

        if lang == self._language_detector.is_english(text):
            self.run_english_presidio(text)
        elif lang == self._language_detector.is_hindi(text):
            self.run_hinglish_presidio(text)
        else:
            pass

    def make(self, validator_config):
        pass

    def run_english_presidio(self, text: str):
        results = self.analyzer.analyze(text=text,
                                entities=self._entity_types,
                                language="en")
        anonymized_text = self.anonymizer.anonymize(text=text,analyzer_results=results)
        return anonymized_text

    def run_hinglish_presidio(self, text: str):
        pass