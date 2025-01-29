# Class to load env variables and set default values

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_USER: str
    DB_NAME: str
    DB_SCHEMA: str
    DB_PORT: int
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    APP_ENV: str = "dev"
    SERVER_PORT: int = 7050

    model_config = SettingsConfigDict(
        env_file=".env", extra="allow"
    )  # uses python-dotenv to load .env file


@lru_cache
def get_settings() -> Settings:
    return Settings()
