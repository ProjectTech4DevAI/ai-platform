import secrets
import warnings
import os
from typing import Any, Literal

from pydantic import (
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    env: str = "development"  # Default value, will be overridden in __init__

    def __init__(self, **kwargs):
        # Determine env_file based on current environment at instantiation time
        env = os.getenv("APP_ENV", "development")
        # Use absolute path to ensure the file is found correctly
        # config.py is in backend/app/core/, so we need to go up 3 levels to reach project root
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        env_file = (
            os.path.join(base_dir, ".env.test")
            if env == "testing"
            else os.path.join(base_dir, ".env")
        )

        # Load the environment file manually to ensure it's loaded correctly
        if os.path.exists(env_file):
            from dotenv import load_dotenv

            load_dotenv(env_file, override=True)

        # Pass env as a keyword argument to override the default
        kwargs["env"] = env
        super().__init__(**kwargs)

    model_config = SettingsConfigDict(
        env_ignore_empty=True,
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 1 days = 1 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ENV(self) -> Literal["testing", "development", "staging", "production"]:
        return self.env  # type: ignore

    PROJECT_NAME: str
    SENTRY_DSN: str = ""
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    # Additional fields from .env files
    ENVIRONMENT: str = "development"  # This is different from the env field
    STACK_NAME: str = ""
    DOCKER_IMAGE_BACKEND: str = ""
    DOCKER_IMAGE_FRONTEND: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48
    EMAIL_TEST_USER: EmailStr

    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = ""
    AWS_S3_BUCKET_PREFIX: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def AWS_S3_BUCKET(self) -> str:
        return f"{self.AWS_S3_BUCKET_PREFIX}-{self.ENV}"

    LOG_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


class SettingsSingleton:
    _instance: Settings | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = Settings()
        return cls._instance

    def __getattr__(self, name):
        return getattr(self._instance, name)

    @classmethod
    def reset(cls):
        """Reset the singleton instance to force recreation."""
        cls._instance = None


# Create settings instance with lazy loading
settings = SettingsSingleton()  # type: ignore
