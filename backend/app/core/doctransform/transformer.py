from abc import ABC, abstractmethod
from pathlib import Path

class Transformer(ABC):
    """Abstract base for document transformers."""

    @abstractmethod
    def transform(self, input_path: Path, output_path: Path) -> Path:
        """
        Transform the document at input_path and write the result to output_path.
        Returns the path to the transformed file.
        """
        pass
