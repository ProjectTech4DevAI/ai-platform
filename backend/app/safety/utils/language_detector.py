from functools import lru_cache
from transformers import pipeline

from app.safety.validators.constants import LANG_HINDI, LANG_ENGLISH, LABEL, SCORE

class LanguageDetector():
    """
    Language detection wrapper over:
    papluca/xlm-roberta-base-language-detection
    Normalizes:
        - hi-Deva → hi
        - hi-Latn → hi
    """

    def __init__(self):
        """
        Initialize the LanguageDetector.
        
        Creates a Hugging Face text-classification pipeline using the `papluca/xlm-roberta-base-language-detection` model (top_k=1) and stores it on `self.lid`. Initializes `self.label` to `None`.
        """
        self.lid = pipeline(
            task = "text-classification",
            model="papluca/xlm-roberta-base-language-detection",
            top_k=1
        )
        self.label = None

    @staticmethod
    def _normalize(label: str) -> str:
        """
        Normalize language labels so variants of the Hindi label map to LANG_HINDI.
        
        Parameters:
            label (str): Language label to normalize.
        
        Returns:
            str: `LANG_HINDI` if `label` starts with `LANG_HINDI`, otherwise returns `label` unchanged.
        """
        return LANG_HINDI if label.startswith(LANG_HINDI) else label

    @lru_cache(maxsize=1024)
    def predict(self, text: str):
        """
        Predict the language of the given text and return a normalized language label with its confidence score.
        
        Parameters:
            text: The input string to classify. If empty or not a string, the function returns an unknown label with zero score.
        
        Returns:
            dict: A mapping with keys `LABEL` (normalized language code; romanized Hindi and Devanagari Hindi are normalized to `'hi'`, or `'unknown'` for invalid input) and `SCORE` (confidence as a float).
        """
        if not text or not isinstance(text, str):
            return {LABEL: "unknown", SCORE: 0.0}

        result = self.lid(text)[0][0]
        score = float(result[SCORE])
        normalized = self._normalize(result[LABEL])

        return {
            LABEL: normalized,
            SCORE: score,
        }

    def is_hindi(self, text: str):
        """
        Determine whether the given text is identified as Hindi.
        
        Parameters:
            text (str): Text to classify for language.
        
        Returns:
            bool: `True` if the predicted language label equals LANG_HINDI, `False` otherwise.
        """
        return self.predict(text)[LABEL] == LANG_HINDI

    def is_english(self, text: str):
        """
        Determine if the detected language of the given text is English.
        
        Parameters:
            text (str): Text to classify.
        
        Returns:
            bool: `True` if the predicted language label is `LANG_ENGLISH`, `False` otherwise.
        """
        return self.predict(text)[LABEL] == LANG_ENGLISH