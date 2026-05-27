import json

from channels.generic.websocket import AsyncWebsocketConsumer


class TenantNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mutuelle_id = self.scope["url_route"]["kwargs"]["mutuelle_id"]
        self.group_name = f"mutuelle_{self.mutuelle_id}_notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
