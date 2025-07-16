import logging
import os
from logging.handlers import RotatingFileHandler
from asgi_correlation_id import correlation_id
from app.core.config import settings

LOG_DIR = settings.LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)

APP_LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")
ERROR_LOG_FILE_PATH = os.path.join(LOG_DIR, "error.log")

LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = (
    "%(asctime)s - [%(correlation_id)s] - %(levelname)s - %(name)s - %(message)s"
)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "N/A"
        return True


# Create root logger
logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)

# Formatter
formatter = logging.Formatter(LOGGING_FORMAT)

# === Stream Handler (Console) ===
stream_handler = logging.StreamHandler()
stream_handler.setLevel(LOGGING_LEVEL)
stream_handler.setFormatter(formatter)
stream_handler.addFilter(CorrelationIdFilter())
logger.addHandler(stream_handler)

# === App Log File Handler (INFO and above) ===
app_file_handler = RotatingFileHandler(
    APP_LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
)
app_file_handler.setLevel(LOGGING_LEVEL)
app_file_handler.setFormatter(formatter)
app_file_handler.addFilter(CorrelationIdFilter())
logger.addHandler(app_file_handler)

# === Error Log File Handler (ERROR and above) ===
error_file_handler = RotatingFileHandler(
    ERROR_LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
)
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(formatter)
error_file_handler.addFilter(CorrelationIdFilter())
logger.addHandler(error_file_handler)
