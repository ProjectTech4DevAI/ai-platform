import logging
import os
from logging.handlers import RotatingFileHandler
from app.core.config import settings

LOG_DIR = settings.LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")

LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

# Create root logger
logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)

# Formatter
formatter = logging.Formatter(LOGGING_FORMAT)

# Stream handler (console)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Rotating file handler
file_handler = RotatingFileHandler(
    LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
