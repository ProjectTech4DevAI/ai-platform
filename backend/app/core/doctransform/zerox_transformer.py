from asyncio import Runner
import logging
from pathlib import Path
from .transformer import Transformer
from pyzerox import zerox

class ZeroxTransformer(Transformer):
    """
    Transformer that uses zerox to extract content from PDFs.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model

    def transform(self, input_path: Path) -> str:
        logging.info(f"ZeroxTransformer: {input_path} (model={self.model})")
        try:
            with Runner() as runner:
                result = runner.run(zerox(
                    file_path=str(input_path),
                    model=self.model,
                ))
            if result is None or not hasattr(result, "pages") or result.pages is None:
                raise RuntimeError("Zerox returned no pages. This may indicate a PDF/image conversion failure (is Poppler installed and in PATH?)")
            output = '\n\n'.join(x.content for x in result.pages)
            if not output:
                raise ValueError('Empty output from zerox')
            return output
        except Exception as e:
            logging.error(
                f"ZeroxTransformer failed for {input_path}: {e}\n"
                "This may be due to a missing Poppler installation or a corrupt PDF file.",
                exc_info=True
            )
            raise RuntimeError(
                f"Failed to extract content from PDF. "
                f"Check that Poppler is installed and in your PATH. Original error: {e}"
            ) from e

