

import os
from celery import Celery
from celery.schedules import crontab
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Celery app configuration
app = Celery('stock_portfolio_tracker')

# Load configuration from environment
app.conf.update(
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    timezone='UTC',
    enable_utc=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
)

# Celery Beat schedule (periodic tasks)
app.conf.beat_schedule = {
    # Update all portfolio prices daily at 4 PM ET (after market close)
    'update-portfolio-prices-daily': {
        'task': 'backend.celery_tasks.update_all_portfolio_prices',
        'schedule': crontab(hour=20, minute=0),  # 4 PM ET = 20:00 UTC
        'options': {'queue': 'default'}
    },
    
    # Calculate portfolio metrics every hour
    'calculate-portfolio-metrics': {
        'task': 'backend.celery_tasks.calculate_all_portfolio_metrics',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'queue': 'default'},
    },
    
    # Fetch historical data weekly (Sunday at 1 AM)
    'fetch-historical-data': {
        'task': 'backend.celery_tasks.fetch_historical_data_task',
        'schedule': crontab(day_of_week=6, hour=1, minute=0),
        'options': {'queue': 'default'},
    },
    
    # Clean up old audit logs monthly (1st of month)
    'cleanup-audit-logs': {
        'task': 'backend.celery_tasks.cleanup_old_audit_logs',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),
        'options': {'queue': 'default'},
    },
}


@app.task(bind=True)
def debug_task(self):
    """Test task for debugging"""
    print(f'Request: {self.request!r}')


@app.task
def test_connection():
    """Test Celery connection"""
    logger.info("Celery connection test successful")
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# Error handling
@app.task(bind=True, max_retries=3)
def task_with_retry(self, *args, **kwargs):
    
    try:
        # Task logic here
        pass
    except Exception as exc:
        logger.error(f"Task failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
