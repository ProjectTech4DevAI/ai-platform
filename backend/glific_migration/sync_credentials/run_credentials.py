from pathlib import Path
from glific_migration.sync_credentials.processor import CredentialProcessor

base_dir = Path(__file__).parent.resolve()


def main():
    input_csv = base_dir / "sample_input.csv"
    output_csv = base_dir / "credentials_output.csv"
    api_url = "http://localhost:8000/api/v1/credentials/"
    api_key = "SuperUserApiKey"
    openai_key = "openai_api_key_example"

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
