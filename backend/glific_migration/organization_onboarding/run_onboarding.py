import logging
from pathlib import Path
from glific_migration.organization_onboarding.processor import OnboardProcessor

base_dir = Path(__file__).parent.resolve()

log_file = base_dir / "onboarding.logs"
logging.basicConfig(
    filename=str(log_file),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting onboarding process...")

    input_file = base_dir / "sample_input.csv"
    output_file = base_dir / "orgs_output.csv"

    OnboardProcessor(
        input_file=str(input_file),
        output_file=str(output_file),
        api_url="http://localhost:8000/api/v1/onboard",
        api_key="api_key",
    ).run()

    logger.info("Onboarding process completed successfully.")


if __name__ == "__main__":
    main()
