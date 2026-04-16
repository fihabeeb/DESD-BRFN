import os

from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BRFN.settings')

app = Celery('BRFN')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


app.conf.beat_schedule = {
    'weekly-payment-settlements': {
        'task': 'payments.tasks.process_weekly_settlements',
        # 'schedule': crontab(day_of_week='monday', hour=0, minute=0),  # sunday midnight / Monday
        'schedule': timedelta(days=1),
        'options': {
            'expires': 86400,  # Task expires after 1 day if not started
        }
    },

    # removes orders that are expired in the db (user left during checkout process)
    'delete-zombie-orders': {
        'task': 'orders.tasks.cleanup_expired_orders',
        # 'schedule': crontab(minute=30),
        'schedule': timedelta(minutes=30),
        'options': {
            'expires': 1500,  # expires 25 mins before.
        }
    },
}