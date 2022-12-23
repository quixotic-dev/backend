from django.conf import settings
import os
import pathlib

from celery import Celery
from kombu import Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quixotic_backend.settings')

app = Celery('quixotic_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.result_expires = (60 * 60 * 8)  # Expire tasks after 8 hours; Default is 24 hours

REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL and not os.environ.get("ECS") and not REDIS_URL.endswith("?ssl_cert_reqs=none"):
    REDIS_URL += "?ssl_cert_reqs=none"

app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_ignore_result=True,
    task_time_limit=600
)

app.autodiscover_tasks([
    "batch_processing.tasks.token",
    "batch_processing.tasks.collection",
    "batch_processing.tasks.common",
    "batch_processing.tasks.scheduler.tasks",
])

# Chron jobs!
