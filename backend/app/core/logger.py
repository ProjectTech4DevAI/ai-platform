import logging
import os
from logging.handlers import RotatingFileHandler
from app.core.config import settings

LOG_DIR = settings.LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)

INFO_LOG_PATH = os.path.join(LOG_DIR, "info.log")
ERROR_LOG_PATH = os.path.join(LOG_DIR, "error.log")

LOGGING_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
formatter = logging.Formatter(LOGGING_FORMAT)

# Create root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Stream handler (console)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Info-level file handler: captures INFO and above
info_handler = RotatingFileHandler(INFO_LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=5)
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(formatter)
logger.addHandler(info_handler)

# Error-level file handler: captures only ERROR and above
error_handler = RotatingFileHandler(ERROR_LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=5)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)
