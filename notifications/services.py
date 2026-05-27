from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import logging

from notifications.models import Notification

logger = logging.getLogger(__name__)


def queue_notification(mutuelle, title, body, channel=Notification.Channel.REALTIME, member=None, recipient_user=None, metadata=None):
    notification = Notification.all_objects.create(
        mutuelle=mutuelle,
        member=member,
        recipient_user=recipient_user,
        channel=channel,
        title=title,
        body=body,
        metadata=metadata or {},
    )
    if channel == Notification.Channel.REALTIME:
        broadcast_notification(notification)
    return notification


def broadcast_notification(notification):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"mutuelle_{notification.mutuelle_id}_notifications",
            {
                "type": "notification",
                "payload": {
                    "id": str(notification.id),
                    "title": notification.title,
                    "body": notification.body,
                    "channel": notification.channel,
                    "status": notification.status,
                },
            },
        )
    except Exception as exc:
        logger.warning("Realtime notification broadcast skipped: %s", exc)
