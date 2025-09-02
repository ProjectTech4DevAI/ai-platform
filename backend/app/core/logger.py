import logging
import os
from logging.handlers import RotatingFileHandler
from asgi_correlation_id import correlation_id
from app.core.config import settings

LOG_DIR = settings.LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")

LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = (
    "%(asctime)s - [%(correlation_id)s] - %(levelname)s - %(name)s - %(message)s"
)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "N/A"
        return True


# Suppress info logs from LiteLLM
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

# Create root logger
logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)

# Formatter
formatter = logging.Formatter(LOGGING_FORMAT)

# Stream handler (console)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.addFilter(CorrelationIdFilter())
logger.addHandler(stream_handler)

# Rotating file handler
file_handler = RotatingFileHandler(
    LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
)
file_handler.setFormatter(formatter)
file_handler.addFilter(CorrelationIdFilter())
logger.addHandler(file_handler)
