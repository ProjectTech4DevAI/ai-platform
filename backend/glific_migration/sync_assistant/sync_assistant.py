from pathlib import Path
import json
from glific_migration.sync_assistant.processor import AssistantIngestProcessor

base_dir = Path(__file__).parent.resolve()


def main():
    with open(base_dir / "../config.json", "r") as file:
        config = json.load(file)

    input_csv = base_dir / config["assistant_ingest"]["input_csv"]
    output_csv = base_dir / config["assistant_ingest"]["output_csv"]
    api_base_url = config["base_url"]

    processor = AssistantIngestProcessor(
        input_file=str(input_csv),
        output_file=str(output_csv),
        base_url=api_base_url,
    )
    processor.run()


if __name__ == "__main__":
    main()
