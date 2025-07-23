from pathlib import Path
from glific_migration.organization_onboarding.processor import OnboardProcessor

base_dir = Path(__file__).parent.resolve()


def main():
    input_file = base_dir / "sample_input.csv"
    output_file = base_dir / "orgs_output.csv"
    api_url = "http://localhost:8000/api/v1/onboard"
    api_key = "SuperUserApiKey"

    processor = OnboardProcessor(
        input_file=str(input_file),
        output_file=str(output_file),
        api_url=api_url,
        api_key=api_key,
    )
    processor.run()


if __name__ == "__main__":
    main()
