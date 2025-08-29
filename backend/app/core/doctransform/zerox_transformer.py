import logging
import tempfile
from pathlib import Path
from asyncio import Runner

from app.core.doctransform.transformer import DocumentTransformer

logger = logging.getLogger(__name__)


class ZeroxTransformer(DocumentTransformer):
    """Document transformer using py-zerox library."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
    
    def supports_formats(self) -> dict:
        """ZeroX supports PDF to markdown transformation."""
        return {
            'pdf': ['markdown']
        }
    
    def transform(self, file_path: str, target_format: str) -> Path:
        """Transform PDF to markdown using ZeroX."""
        try:
            from pyzerox import zerox
        except ImportError:
            raise ImportError("py-zerox library not installed. Please install with: pip install py-zerox")
        
        logger.info(f"Starting ZeroX transformation for file {file_path}")
        
        try:
            with Runner() as runner:
                result = runner.run(zerox(
                    file_path=file_path,
                    model=self.model,
                ))
            
            if result is None or not hasattr(result, "pages") or result.pages is None:
                raise RuntimeError("Zerox returned no pages. This may indicate a PDF/image conversion failure (is Poppler installed and in PATH?)")
            
            output = '\n\n'.join(x.content for x in result.pages)
            if not output:
                raise ValueError('Empty output from zerox')
            
            # Write output to temporary file
            file_extension = 'md' if target_format == 'markdown' else target_format
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=f'.{file_extension}', delete=False, encoding='utf-8')
            temp_file.write(output)
            temp_file.close()
            
            logger.info(f"ZeroX transformation completed for file {file_path}")
            return Path(temp_file.name)
            
        except Exception as e:
            logger.error(
                f"ZeroxTransformer failed for {file_path}: {e}\n"
                "This may be due to a missing Poppler installation or a corrupt PDF file.",
                exc_info=True
            )
            raise RuntimeError(
                f"Failed to extract content from PDF. "
                f"Check that Poppler is installed and in your PATH. Original error: {e}"
            ) from e         


