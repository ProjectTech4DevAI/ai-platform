import logging
from pathlib import Path
from glific_migration.sync_assistant.processor import AssistantIngestProcessor

base_dir = Path(__file__).parent.resolve()
log_file = base_dir / "sync_assistant.logs"
logging.basicConfig(
    filename=str(log_file),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    input_csv = base_dir / "sample_input.csv"
    output_csv = base_dir / "assistants_output.csv"
    api_base_url = "http://localhost:8000/api/v1"

    processor = AssistantIngestProcessor(
        input_file=input_csv,
        output_file=output_csv,
        base_url=api_base_url
    )
    processor.run()
