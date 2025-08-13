from abc import ABC, abstractmethod
from pathlib import Path

class Transformer(ABC):
    """Abstract base for document transformers."""

    @abstractmethod
    def transform(self, input_path: Path) -> str:
        """
        Transform the document at input_path and return the result as text.
        """
        pass
