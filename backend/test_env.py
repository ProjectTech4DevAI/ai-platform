from pydantic_settings import BaseSettings
import os


class TestSettings(BaseSettings):
    SECRET_KEY: str = "default"

    model_config = {
        "env_file": "/Users/akhileshnegi/Projects/ai-platform/.env.test",
        "extra": "ignore",
    }


if __name__ == "__main__":
    os.environ["APP_ENV"] = "testing"
    s = TestSettings()
    print(f"SECRET_KEY: {s.SECRET_KEY}")
