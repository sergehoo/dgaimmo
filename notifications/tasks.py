from django.utils import timezone

from config.celery import app
from notifications.models import Notification
from notifications.services import broadcast_notification


@app.task
def deliver_notification(notification_id):
    notification = Notification.all_objects.get(id=notification_id)
    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.metadata = {**notification.metadata, "delivery": "simulated"}
    notification.save(update_fields=["status", "sent_at", "metadata", "updated_at"])
    if notification.channel == Notification.Channel.REALTIME:
        broadcast_notification(notification)
    return str(notification.id)
