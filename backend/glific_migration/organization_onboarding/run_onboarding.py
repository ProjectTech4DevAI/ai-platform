from pathlib import Path
import json
from glific_migration.organization_onboarding.processor import OnboardProcessor

base_dir = Path(__file__).parent.resolve()


def main():
    with open(base_dir / "../config.json", "r") as file:
        config = json.load(file)

    input_file = base_dir / config["organization_onboarding"]["input_csv"]
    output_file = base_dir / config["organization_onboarding"]["output_csv"]
    api_url = config["base_url"] + "/onboard"
    api_key = config["api_key"]

    processor = OnboardProcessor(
        input_file=str(input_file),
        output_file=str(output_file),
        api_url=api_url,
        api_key=api_key,
    )
    processor.run()


if __name__ == "__main__":
    main()
