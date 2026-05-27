from core.serializers import TenantModelSerializer
from notifications.models import Notification


class NotificationSerializer(TenantModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ["mutuelle", "sent_at"]
