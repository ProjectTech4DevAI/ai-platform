from pathlib import Path
from .transformer import Transformer

class NoOpTransformer(Transformer):
    """
    A no-op transformer that just returns the file contents.
    """

    def transform(self, input_path: Path) -> str:
        return input_path.read_text()
        output_path.write_text(input_path.read_text())
