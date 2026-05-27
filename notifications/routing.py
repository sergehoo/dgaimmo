from django.urls import re_path

from notifications.consumers import TenantNotificationConsumer

websocket_urlpatterns = [
    re_path(r"ws/mutuelles/(?P<mutuelle_id>[0-9a-f-]+)/notifications/$", TenantNotificationConsumer.as_asgi()),
]
