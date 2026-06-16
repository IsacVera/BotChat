import os
from celery import Celery

# Set default Django settings for Celery workers
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testbackend.settings")

celery_app = Celery("testbackend")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")
celery_app.autodiscover_tasks()

# Alias as `app` so Celery CLI can find it with `-A testbackend.celery_app`
app = celery_app

__all__ = ("celery_app", "app")
