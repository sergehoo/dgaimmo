from django.db import models

from core.models import TenantModel


class Notification(TenantModel):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        PUSH = "push", "Push"
        REALTIME = "realtime", "Temps réel"

    class Status(models.TextChoices):
        QUEUED = "queued", "En file"
        SENT = "sent", "Envoyée"
        FAILED = "failed", "Échouée"

    recipient_user = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    member = models.ForeignKey("memberships.Member", on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.CharField(max_length=24, choices=Channel.choices, db_index=True)
    title = models.CharField(max_length=160)
    body = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
