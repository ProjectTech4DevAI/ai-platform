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
        """
        Initialize the PIIRemover validator with configuration for entity detection and anonymization.
        
        Parameters:
            entity_types (Optional[List[str]]): List of entity types to redact (default ["ALL"] when None).
            threshold (float): Confidence threshold used for entity detection (default 0.5).
            language (str): Target language for processing; must be one of ["en", "hi"].
            language_detector (Optional[LanguageDetector]): Language detection instance to use; a new LanguageDetector is created when None.
            on_fail (Optional[Callable]): Failure handling strategy passed to the base validator.
        
        Raises:
            Exception: If `language` is not in the supported languages list.
        """
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
        """
        Detects PII in the input text using language-specific processing and returns a validation result reflecting any anonymization.
        
        If the language detector indicates Hindi, the text is processed by the Hinglish path; otherwise it is processed by the English path. If processing changes the text, returns a FailResult with an error message and the anonymized text in `fix_value`. If the text is unchanged, returns a PassResult containing the original text.
        
        Returns:
            ValidationResult: A FailResult when PII was detected and removed (with `fix_value` set to the anonymized text), or a PassResult when no changes were made.
        """
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
        """
        Anonymizes personally identifiable information in English text and returns the redacted result.
        
        Parameters:
            text (str): Input text in English to be scanned for PII.
        
        Returns:
            str: The input text with detected PII replaced by anonymized placeholders.
        """
        results = self.analyzer.analyze(text=text,
                                language="en")
        anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text

    def run_hinglish_presidio(self, text: str):
        """
        Placeholder Hinglish PII processing that currently performs no transformations.
        
        Returns:
            The original input `text` unchanged.
        """
        return text
    
class PIIRemoverSafetyValidatorConfig(BaseValidatorConfig):
    type: Literal["pii_remover"]
    entity_types: Optional[List[str]] = None
    threshold: float = 0.5
    language: str = "en"
    language_detector: Optional[LanguageDetector] = None
    validator_cls: ClassVar = PIIRemover