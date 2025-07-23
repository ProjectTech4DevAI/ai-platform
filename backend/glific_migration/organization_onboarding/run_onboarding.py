import logging
from .processor import OnboardingProcessor

logging.basicConfig(
    filename='onboarding.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

def main():
    input_filename = 'sample_input.csv'
    output_filename = 'output_onboarding.csv'
    api_url = 'http://localhost:8000/api/v1/onboard'
    api_key = 'test_api_key'

    processor = OnboardingProcessor(input_filename, output_filename, api_url, api_key)
    processor.run()

if __name__ == "__main__":
    main()
