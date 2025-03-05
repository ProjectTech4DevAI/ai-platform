import os
from enum import Enum
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env if running locally
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

if ENVIRONMENT == "local" and os.path.exists(".env"):
    load_dotenv()


class AppSettings(BaseSettings):
    APP_NAME: str = os.getenv("APP_NAME", "FastAPI app")
    APP_DESCRIPTION: str | None = os.getenv("APP_DESCRIPTION", None)
    APP_VERSION: str | None = os.getenv("APP_VERSION", None)
    LICENSE_NAME: str | None = os.getenv("LICENSE", None)
    CONTACT_NAME: str | None = os.getenv("CONTACT_NAME", None)
    CONTACT_EMAIL: str | None = os.getenv("CONTACT_EMAIL", None)


class CryptSettings(BaseSettings):
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-secret")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))


class DatabaseSettings(BaseSettings):
    pass


class SQLiteSettings(DatabaseSettings):
    SQLITE_URI: str = os.getenv("SQLITE_URI", "./sql_app.db")
    SQLITE_SYNC_PREFIX: str = os.getenv("SQLITE_SYNC_PREFIX", "sqlite:///")
    SQLITE_ASYNC_PREFIX: str = os.getenv("SQLITE_ASYNC_PREFIX", "sqlite+aiosqlite:///")


class MySQLSettings(DatabaseSettings):
    MYSQL_USER: str = os.getenv("MYSQL_USER", "username")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "password")
    MYSQL_SERVER: str = os.getenv("MYSQL_SERVER", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 5432))
    MYSQL_DB: str = os.getenv("MYSQL_DB", "dbname")
    MYSQL_SYNC_PREFIX: str = os.getenv("MYSQL_SYNC_PREFIX", "mysql://")
    MYSQL_ASYNC_PREFIX: str = os.getenv("MYSQL_ASYNC_PREFIX", "mysql+aiomysql://")
    MYSQL_URL: str | None = os.getenv("MYSQL_URL", None)

    # Construct full DB URI
    MYSQL_URI: str = f"{MYSQL_SYNC_PREFIX}{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_SERVER}:{MYSQL_PORT}/{MYSQL_DB}"


class PostgresSettings(DatabaseSettings):
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "postgres")
    POSTGRES_SYNC_PREFIX: str = os.getenv("POSTGRES_SYNC_PREFIX", "postgresql://")
    POSTGRES_ASYNC_PREFIX: str = os.getenv("POSTGRES_ASYNC_PREFIX", "postgresql+asyncpg://")
    POSTGRES_URL: str | None = os.getenv("POSTGRES_URL", None)

    # Construct full DB URI
    POSTGRES_URI: str = f"{POSTGRES_SYNC_PREFIX}{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"


class FirstUserSettings(BaseSettings):
    ADMIN_NAME: str = os.getenv("ADMIN_NAME", "admin")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@admin.com")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "!Ch4ng3Th1sP4ssW0rd!")


class RedisCacheSettings(BaseSettings):
    REDIS_CACHE_HOST: str = os.getenv("REDIS_CACHE_HOST", "localhost")
    REDIS_CACHE_PORT: int = int(os.getenv("REDIS_CACHE_PORT", 6379))
    REDIS_CACHE_URL: str = f"redis://{REDIS_CACHE_HOST}:{REDIS_CACHE_PORT}"


class ClientSideCacheSettings(BaseSettings):
    CLIENT_CACHE_MAX_AGE: int = int(os.getenv("CLIENT_CACHE_MAX_AGE", 60))


class RedisQueueSettings(BaseSettings):
    REDIS_QUEUE_HOST: str = os.getenv("REDIS_QUEUE_HOST", "localhost")
    REDIS_QUEUE_PORT: int = int(os.getenv("REDIS_QUEUE_PORT", 6379))


class RedisRateLimiterSettings(BaseSettings):
    REDIS_RATE_LIMIT_HOST: str = os.getenv("REDIS_RATE_LIMIT_HOST", "localhost")
    REDIS_RATE_LIMIT_PORT: int = int(os.getenv("REDIS_RATE_LIMIT_PORT", 6379))
    REDIS_RATE_LIMIT_URL: str = f"redis://{REDIS_RATE_LIMIT_HOST}:{REDIS_RATE_LIMIT_PORT}"


class DefaultRateLimitSettings(BaseSettings):
    DEFAULT_RATE_LIMIT_LIMIT: int = int(os.getenv("DEFAULT_RATE_LIMIT_LIMIT", 10))
    DEFAULT_RATE_LIMIT_PERIOD: int = int(os.getenv("DEFAULT_RATE_LIMIT_PERIOD", 3600))


class EnvironmentOption(Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentSettings(BaseSettings):
    ENVIRONMENT: EnvironmentOption = EnvironmentOption(os.getenv("ENVIRONMENT", "local"))


class OPENSettings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")


class Settings(
    AppSettings,
    PostgresSettings,
    CryptSettings,
    FirstUserSettings,
    EnvironmentSettings,
    RedisCacheSettings,
    ClientSideCacheSettings,
    RedisQueueSettings,
    RedisRateLimiterSettings,
    DefaultRateLimitSettings,
    OPENSettings,
):
    pass


settings = Settings()
