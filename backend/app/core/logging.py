import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

# Default logging configuration
DEFAULT_CONFIG = {
    "LOG_LEVEL": "INFO",
    "ENVIRONMENT": "development",
    "LOG_FORMAT": "text"
}

class LogConfig:
    """Logging Configuration"""
    
    # Log levels mapping
    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    def __init__(self):
        # Base directory for logs
        self.log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        self.ensure_log_directory()

        # Log file settings
        self.log_file = os.path.join(self.log_dir, "app.log")
        self.max_bytes = 10 * 1024 * 1024  # 10MB
        self.backup_count = 5
        
        # Get environment and format settings with defaults
        try:
            from app.core.config import settings
            self.environment = getattr(settings, "ENVIRONMENT", DEFAULT_CONFIG["ENVIRONMENT"])
            log_level = getattr(settings, "LOG_LEVEL", DEFAULT_CONFIG["LOG_LEVEL"])
        except ImportError:
            self.environment = DEFAULT_CONFIG["ENVIRONMENT"]
            log_level = DEFAULT_CONFIG["LOG_LEVEL"]
        
        # Logging format based on environment
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if self.environment == "production":
            self.log_format = (
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s"}'
            )

        # Set log level with fallback
        self.log_level = self.LEVEL_MAP.get(
            log_level.upper(),
            logging.INFO
        )

    def ensure_log_directory(self) -> None:
        """Ensure log directory exists"""
        try:
            os.makedirs(self.log_dir, exist_ok=True)
        except Exception as e:
            sys.stderr.write(f"Error creating log directory: {str(e)}\n")
            raise

    def get_file_handler(self) -> RotatingFileHandler:
        """Configure and return file handler"""
        try:
            handler = RotatingFileHandler(
                filename=self.log_file,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            handler.setLevel(self.log_level)
            handler.setFormatter(logging.Formatter(self.log_format))
            return handler
        except Exception as e:
            sys.stderr.write(f"Error setting up file handler: {str(e)}\n")
            raise

    def get_console_handler(self) -> logging.StreamHandler:
        """Configure and return console handler"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.log_level)
        handler.setFormatter(logging.Formatter(self.log_format))
        return handler

def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Set up and return a logger instance
    
    Args:
        name: Logger name (optional)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    try:
        # Initialize config
        config = LogConfig()
        
        # Get or create logger
        logger = logging.getLogger(name or "")
        logger.setLevel(config.log_level)
        
        # Remove existing handlers
        logger.handlers = []
        
        # Add handlers
        logger.addHandler(config.get_file_handler())
        if config.environment != "production":
            logger.addHandler(config.get_console_handler())
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        return logger
    
    except Exception as e:
        # Fallback to basic logging if setup fails
        basic_logger = logging.getLogger(name or "")
        basic_logger.setLevel(logging.INFO)
        if not basic_logger.handlers:
            basic_logger.addHandler(logging.StreamHandler(sys.stdout))
        basic_logger.error(f"Error setting up logger: {str(e)}")
        return basic_logger

def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name (defaults to module name)
    
    Returns:
        logging.Logger: Logger instance
    """
    return setup_logger(name)

# Initialize root logger with fallback handling
try:
    root_logger = setup_logger()
except Exception as e:
    # Setup basic logging if initialization fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    root_logger = logging.getLogger()
    root_logger.error(f"Failed to initialize custom logging: {str(e)}")

# Example usage:
# logger = get_logger(__name__)
# logger.info("Application started")
# logger.error("An error occurred", exc_info=True)