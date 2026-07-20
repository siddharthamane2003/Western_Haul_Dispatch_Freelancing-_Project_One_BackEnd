from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "western_haul",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.workers.tasks.send_email": {"queue": "emails"},
        "app.workers.tasks.send_sms": {"queue": "sms"},
        "app.workers.tasks.send_whatsapp": {"queue": "whatsapp"},
        "app.workers.tasks.generate_report_pdf": {"queue": "reports"},
    },
    beat_schedule={},
)

celery_app.autodiscover_tasks(["app.workers"])
