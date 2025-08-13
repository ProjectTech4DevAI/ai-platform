from pathlib import Path
from typing import Type, Dict, Set, Tuple, Optional

from .transformer import Transformer
from .test_transformer import TestTransformer
from .zerox_transformer import ZeroxTransformer

class TransformationError(Exception):
    """Raised when a document transformation fails."""

# Map transformer names to their classes
TRANSFORMERS: Dict[str, Type[Transformer]] = {
    "default": ZeroxTransformer,
    "test": TestTransformer,
    "zerox": ZeroxTransformer,
}

# Define supported transformations: (source_format, target_format) -> [available_transformers]
SUPPORTED_TRANSFORMATIONS: Dict[Tuple[str, str], Dict[str, str]] = {
    ("pdf", "markdown"): {
        "default": "zerox",
        "zerox": "zerox",
    },
    # Future transformations can be added here
    # ("docx", "markdown"): {"default": "pandoc", "pandoc": "pandoc"},
    # ("html", "markdown"): {"default": "pandoc", "pandoc": "pandoc"},
}

# Map file extensions to format names
EXTENSION_TO_FORMAT: Dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc", 
    ".html": "html",
    ".htm": "html",
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
}

# Map format names to file extensions
FORMAT_TO_EXTENSION: Dict[str, str] = {
    "pdf": ".pdf",
    "docx": ".docx",
    "doc": ".doc",
    "html": ".html",
    "text": ".txt",
    "markdown": ".md",
}

def get_file_format(filename: str) -> str:
    """Extract format from filename extension."""
    ext = Path(filename).suffix.lower()
    format_name = EXTENSION_TO_FORMAT.get(ext)
    if not format_name:
        raise ValueError(f"Unsupported file extension: {ext}")
    return format_name

def get_supported_transformations() -> Dict[Tuple[str, str], Set[str]]:
    """Get all supported transformation combinations."""
    return {
        key: set(transformers.keys()) 
        for key, transformers in SUPPORTED_TRANSFORMATIONS.items()
    }

def is_transformation_supported(source_format: str, target_format: str) -> bool:
    """Check if a transformation from source_format to target_format is supported."""
    return (source_format, target_format) in SUPPORTED_TRANSFORMATIONS

def get_available_transformers(source_format: str, target_format: str) -> Dict[str, str]:
    """Get available transformers for a specific transformation."""
    return SUPPORTED_TRANSFORMATIONS.get((source_format, target_format), {})

def resolve_transformer(source_format: str, target_format: str, transformer_name: Optional[str] = None) -> str:
    """
    Resolve the actual transformer to use for a transformation.
    Returns the transformer name to use.
    """
    available_transformers = get_available_transformers(source_format, target_format)
    
    if not available_transformers:
        raise ValueError(
            f"Transformation from {source_format} to {target_format} is not supported"
        )
    
    if transformer_name is None:
        transformer_name = "default"
    
    if transformer_name not in available_transformers:
        available = ", ".join(available_transformers.keys())
        raise ValueError(
            f"Transformer '{transformer_name}' not available for {source_format} to {target_format}. "
            f"Available: {available}"
        )
    
    return available_transformers[transformer_name]

def convert_document(input_path: Path, transformer_name: str = "default") -> str:
    """
    Select and run the specified transformer on the input_path, returning text.
    """
    try:
        transformer_cls = TRANSFORMERS[transformer_name]
    except KeyError:
        available = ", ".join(TRANSFORMERS.keys())
        raise ValueError(f"Transformer '{transformer_name}' not found. Available: {available}")

    transformer = transformer_cls()
    try:
        return transformer.transform(input_path)
    except Exception as e:
        raise TransformationError(
            f"Error applying transformer '{transformer_name}': {e}"
        ) from e
