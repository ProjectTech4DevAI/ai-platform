from pathlib import Path
from .transformer import Transformer

class TestTransformer(Transformer):
    """
    A test transformer that returns a hardcoded lorem ipsum string.
    """

    def transform(self, input_path: Path, output_path: Path) -> Path:
        content = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        )
        output_path.write_text(content, encoding='utf-8')
        return output_path
