import logging
from pathlib import Path
from .transformer import Transformer

# Assume pyzerox and zerox are installed and available
from pyzerox import zerox

class ZeroxTransformer(Transformer):
    """
    Transformer that uses zerox to extract content from PDFs.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model

    def transform(self, input_path: Path, output_path: Path) -> None:
        # Import Runner here to avoid import errors if not available globally
        from pyzerox import Runner

        logging.info(f"ZeroxTransformer: {input_path} -> {output_path} (model={self.model})")
        with Runner() as runner:
            result = runner.run(zerox(
                file_path=str(input_path),
                model=self.model,
            ))
        output = '\n\n'.join(x.content for x in result.pages)
        if not output:
            raise ValueError('Empty output from zerox')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
