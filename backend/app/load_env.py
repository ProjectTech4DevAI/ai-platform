import os
from dotenv import load_dotenv


def load_environment():
    env = os.getenv("ENVIRONMENT", "development")

    # Use the same path as config.py expects (one level above backend/)
    env_file = "../.env"
    if env == "testing":
        env_file = "../.env.test"

    load_dotenv(env_file)
