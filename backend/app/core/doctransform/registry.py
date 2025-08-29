import logging
from pathlib import Path
from typing import Dict, Type, Optional
from app.core.doctransform.transformer import DocumentTransformer

logger = logging.getLogger(__name__)


class TransformationError(Exception):
    """Raised when a document transformation fails."""


# Registry of transformers
TRANSFORMER_REGISTRY: Dict[str, Type[DocumentTransformer]] = {}

# Supported file formats
SUPPORTED_FORMATS = {
    'pdf': ['.pdf'],
    'markdown': ['.md', '.markdown'],
    'text': ['.txt'],
    'docx': ['.docx'],
    'html': ['.html', '.htm'],
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


def register_transformer(name: str, transformer_class: Type[DocumentTransformer]):
    """Register a transformer class."""
    TRANSFORMER_REGISTRY[name] = transformer_class
    logger.info(f"Registered transformer: {name}")


def get_file_format(filename: str) -> str:
    """Determine file format from filename."""
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    suffix = Path(filename).suffix.lower()
    
    for format_name, extensions in SUPPORTED_FORMATS.items():
        if suffix in extensions:
            return format_name
    
    raise ValueError(f"Unsupported file format: {suffix}")


def is_transformation_supported(source_format: str, target_format: str) -> bool:
    """Check if transformation between formats is supported."""
    for transformer_class in TRANSFORMER_REGISTRY.values():
        transformer = transformer_class()
        supported = transformer.supports_formats()
        if source_format in supported and target_format in supported[source_format]:
            return True
    return False


def get_available_transformers(source_format: str, target_format: str) -> Dict[str, Type[DocumentTransformer]]:
    """Get all transformers that support the given format transformation."""
    available = {}
    
    for name, transformer_class in TRANSFORMER_REGISTRY.items():
        transformer = transformer_class()
        supported = transformer.supports_formats()
        if source_format in supported and target_format in supported[source_format]:
            available[name] = transformer_class
    
    return available


def resolve_transformer(source_format: str, target_format: str, transformer_name: Optional[str] = None) -> Type[DocumentTransformer]:
    """Resolve the transformer to use for a given transformation."""
    available_transformers = get_available_transformers(source_format, target_format)
    
    if not available_transformers:
        raise ValueError(f"No transformers available for {source_format} to {target_format}")
    
    if transformer_name is None or transformer_name == "default":
        # Return the first available transformer
        return next(iter(available_transformers.values()))
    
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
        transformer_cls = TRANSFORMER_REGISTRY[transformer_name]
    except KeyError:
        available = ", ".join(TRANSFORMER_REGISTRY.keys())
        raise ValueError(f"Transformer '{transformer_name}' not found. Available: {available}")

    transformer = transformer_cls()
    try:
        # For backward compatibility, assume markdown as target format
        result_path = transformer.transform(str(input_path), "markdown")
        with open(result_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise TransformationError(
            f"Error applying transformer '{transformer_name}': {e}"
        ) from e


# Import and register transformers
try:
    from app.core.doctransform.zerox_transformer import ZeroxTransformer
    register_transformer("zerox", ZeroxTransformer)
    register_transformer("default", ZeroxTransformer)  # Set as default
except ImportError:
    logger.warning("ZeroxTransformer not available")

try:
    from app.core.doctransform.test_transformer import TestTransformer
    register_transformer("test", TestTransformer)
except ImportError:
    logger.warning("TestTransformer not available")
