from pathlib import Path
import json
from glific_migration.sync_credentials.processor import CredentialProcessor

base_dir = Path(__file__).parent.resolve()


def main():
    with open(base_dir / "../config.json", "r") as file:
        config = json.load(file)

    input_csv = base_dir / config["sync_credentials"]["input_csv"]
    output_csv = base_dir / config["sync_credentials"]["output_csv"]
    api_url = config["base_url"] + "/credentials/"
    api_key = config["api_key"]
    openai_key = config["openai_key"]

    processor = CredentialProcessor(
        input_file=str(input_csv),
        output_file=str(output_csv),
        api_url=api_url,
        api_key=api_key,
        openai_key=openai_key,
    )
    processor.run()


if __name__ == "__main__":
    main()
