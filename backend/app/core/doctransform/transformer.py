from abc import ABC, abstractmethod
from pathlib import Path


class DocumentTransformer(ABC):
    """Base class for document transformers."""
    
    @abstractmethod
    def transform(self, file_path: str, target_format: str) -> Path:
        """
        Transform a document from one format to another.
        
        Args:
            file_path: Path to the source document file
            target_format: Target format (e.g., 'markdown', 'pdf')
            
        Returns:
            Path to a file containing the transformed content
        """
        pass
    
    @abstractmethod
    def supports_formats(self) -> dict:
        """
        Return a dictionary of supported format transformations.
        
        Returns:
            Dict with source formats as keys and list of target formats as values
        """
        pass

