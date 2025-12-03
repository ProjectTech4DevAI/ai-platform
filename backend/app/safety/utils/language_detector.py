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
        self.lid = pipeline(
            task = "text-classification",
            model="papluca/xlm-roberta-base-language-detection",
            top_k=1
        )
        self.label = None

    @staticmethod
    def _normalize(label: str) -> str:
        return LANG_HINDI if label.startswith(LANG_HINDI) else label

    @lru_cache(maxsize=1024)
    def predict(self, text: str):
        """
        Returns normalized language + raw confidence.
        Romanized Hindi and Hindi (Devanagari) both → 'hi'.
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
        return self.predict(text)[LABEL] == LANG_HINDI

    def is_english(self, text: str):
        return self.predict(text)[LABEL] == LANG_ENGLISH