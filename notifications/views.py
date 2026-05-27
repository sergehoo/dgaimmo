from rest_framework import viewsets

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.select_related("recipient_user", "member")
    serializer_class = NotificationSerializer
    filterset_fields = ["channel", "status"]
    search_fields = ["title", "body"]
