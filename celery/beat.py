#!/usr/bin/env python3
"""
Celery beat scheduler for cron jobs.
"""
import os
import sys

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from celery.bin import beat
from celery_app import celery_app

def start_beat(loglevel: str = "info"):
    """
    Start Celery beat scheduler.
    
    Args:
        loglevel: Logging level
    """
    print(f"Starting Celery beat scheduler")
    print(f"Log level: {loglevel}")
    
    # Start the beat scheduler
    beat_instance = beat.beat(app=celery_app)
    beat_instance.run(loglevel=loglevel)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Start Celery beat scheduler")
    parser.add_argument(
        "--loglevel",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    start_beat(args.loglevel)
