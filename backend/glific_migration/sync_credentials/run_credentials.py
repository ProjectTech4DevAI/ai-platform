import logging
from pathlib import Path
from glific_migration.sync_credentials.processor import CredentialProcessor

# Resolve script's base directory
base_dir = Path(__file__).parent.resolve()

# Log file inside same folder
log_file = base_dir / "credentials.logs"
logging.basicConfig(
    filename=str(log_file),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":

    input_csv = base_dir / "sample_input.csv"
    output_csv = base_dir / "credentials_output.csv"

    api_url = "http://localhost:8000/api/v1/credentials/"
    api_key = "api_key"
    openai_key = "adfgdasfds"

    processor = CredentialProcessor(
        input_file=str(input_csv),
        output_file=str(output_csv),
        api_url=api_url,
        api_key=api_key,
        openai_key=openai_key
    )
    processor.run()
