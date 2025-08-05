from pathlib import Path
from .transformer import Transformer

class NoOpTransformer(Transformer):
    """
    A no-op transformer that just reads and writes the file contents.
    TODO: remove once real transformer is in place; used for plumbing tests.
    """

    def transform(self, input_path: Path, output_path: Path) -> None:
        output_path.write_text(input_path.read_text())
