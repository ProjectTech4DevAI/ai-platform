from pathlib import Path
from glific_migration.sync_assistant.processor import AssistantIngestProcessor

base_dir = Path(__file__).parent.resolve()


def main():
    input_csv = base_dir / "sample_input.csv"
    output_csv = base_dir / "assistants_output.csv"
    api_base_url = "http://localhost:8000/api/v1"

    processor = AssistantIngestProcessor(
        input_file=str(input_csv),
        output_file=str(output_csv),
        base_url=api_base_url,
    )
    processor.run()


if __name__ == "__main__":
    main()
