from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "code_compliance",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.file_processing"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
)
