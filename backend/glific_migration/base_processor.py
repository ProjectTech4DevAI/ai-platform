import csv
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class BaseCSVProcessor(ABC):
    """Base class for CSV processing with common functionality."""

    def __init__(self, input_file: str, output_file: str, headers: List[str]):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.headers = headers
        self._setup_logging()
        self._init_output_csv()

    def _setup_logging(self) -> None:
        """Configure logging for the processor."""
        log_file = self.output_file.parent / f"{self.__class__.__name__.lower()}.logs"
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )

        logging.getLogger().addHandler(console_handler)

    def _init_output_csv(self) -> None:
        """Initialize CSV file with headers."""
        try:
            with open(self.output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
        except Exception as e:
            logger.error(f"Error initializing output file {self.output_file}: {str(e)}")
            raise

    def load_csv(self) -> List[Dict[str, str]]:
        """Load CSV file into list of dictionaries."""
        try:
            with open(self.input_file, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except FileNotFoundError:
            logger.error(f"Input file not found: {self.input_file}")
            raise
        except Exception as e:
            logger.error(f"Error reading CSV file {self.input_file}: {str(e)}")
            raise

    def append_to_csv(self, row: Dict[str, str]) -> None:
        """Append a single row to the output CSV."""
        try:
            with open(self.output_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerow(row)
        except Exception as e:
            logger.error(f"Error appending to output file {self.output_file}: {str(e)}")
            raise

    @abstractmethod
    def validate_csv(self, rows: List[Dict[str, str]]) -> bool:
        """Validate CSV data before processing."""
        pass

    @abstractmethod
    def process_rows(self, rows: List[Dict[str, str]]) -> None:
        """Process CSV rows and write results incrementally."""
        pass

    def run(self) -> None:
        """Execute the complete processing pipeline."""
        logger.info(f"Starting {self.__class__.__name__}...")
        try:
            rows = self.load_csv()
            if not self.validate_csv(rows):
                logger.error("Validation failed. Aborting processing.")
                return
            self.process_rows(rows)
            logger.info(f"{self.__class__.__name__} completed successfully.")
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}", exc_info=True)
            raise
