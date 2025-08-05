from pathlib import Path
from typing import Dict, Type

from .transformer import Transformer
from .noop_transformer import NoOpTransformer
from .zerox_transformer import ZeroxTransformer

class TransformationError(Exception):
    """Raised when a document transformation fails."""

# Map transformer names to their classes
TRANSFORMERS: Dict[str, Type[Transformer]] = {
    "default": NoOpTransformer,
    "noop": NoOpTransformer,
    "zerox": ZeroxTransformer,
}

def convert_document(input_path: Path, output_path: Path, transformer_name: str = "default") -> None:
    """
    Select and run the specified transformer on the input_path, writing to output_path.
    """
    try:
        transformer_cls = TRANSFORMERS[transformer_name]
    except KeyError:
        available = ", ".join(TRANSFORMERS.keys())
        raise ValueError(f"Transformer '{transformer_name}' not found. Available: {available}")

    transformer = transformer_cls()
    try:
        transformer.transform(input_path, output_path)
    except Exception as e:
        raise TransformationError(
            f"Error applying transformer '{transformer_name}': {e}"
        ) from e
