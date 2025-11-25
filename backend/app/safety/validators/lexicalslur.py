from enum import Enum
from ..validator import Validator

import emoji
import ftfy
import pandas
import re
import string
import unicodedata

class SlurSeverity(Enum):
    Low = "low"
    Medium = "medium"
    High = "high"
    All = "all"

class LexicalSlur(Validator):
    """
    Validate text for the presence of lexical slurs using a predefined list.
    """

    def __init__(self):
        self.slur_list = []
        self.text = None
        self.severity = SlurSeverity.All
        self.languages = []
        pass

    def make(self, validator_config):
        if validator_config.params.has_key("severity"):
            self.severity = SlurSeverity(validator_config.params["severity"])

        if validator_config.params.has_key("languages"):
            self.languages = validator_config.params["languages"]
        
        self.slur_list = self.load_slur_list()

    def execute(self, text: str):
        self.text = text
        self.text = self.remove_emojis(self.text)
        self.text = self.remove_nos(self.text)
        self.text = self.clean_text(self.text)
        words = self.text.split()
        detected_slurs = []

        for slur in self.slur_list:
            if slur in words:
                if slur not in detected_slurs:
                    detected_slurs.append(slur)
        # if len(detected_slurs) == 0:
        #     return None
        # return detected_slurs

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
        file_path = "../Curated_Slurlist_Hindi_English.csv"
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
