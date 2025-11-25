from transformers import pipeline

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
            "text-classification",
            model="papluca/xlm-roberta-base-language-detection",
            top_k=1
        )
        self.label = None

    def predict(self, text: str):
        """
        Returns normalized language + raw confidence.
        Romanized Hindi and Hindi (Devanagari) both → 'hi'.
        """
        if not text or not isinstance(text, str):
            return {"label": "unknown", "score": 0.0}

        result = self.lid(text)[0]
        raw_label = result["label"]
        score = float(result["score"])

        # Normalize: Romanized Hindi & Hindi → hi
        if raw_label.startswith("hi"):
            normalized = "hi"
        else:
            normalized = raw_label

        self.label = {"label": normalized, "score": score, "raw_label": raw_label}
        return self.label

    def is_hindi(self, text: str):
        if self.label is None:
            return self.predict(text)["label"] == "hi"
        return self.label["label"] == "hi"

    def is_english(self, text: str):
        if self.label is None:
            return self.predict(text)["label"] == "en"
        return self.label["label"] == "en"