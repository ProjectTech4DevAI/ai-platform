from .celery_app import celery_app

# Import monitoring to register signal handlers
from . import monitoring

__all__ = ["celery_app"]
