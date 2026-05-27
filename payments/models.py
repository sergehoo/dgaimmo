from django.db import models

from core.models import MoneyModel, TenantModel


class Payment(TenantModel, MoneyModel):
    class Provider(models.TextChoices):
        ORANGE = "orange_money", "Orange Money"
        MTN = "mtn_money", "MTN Money"
        WAVE = "wave", "Wave"
        MOOV = "moov_money", "Moov Money"
        CASH = "cash", "Espèces"
        BANK = "bank", "Banque"

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initialisé"
        PENDING = "pending", "En attente"
        SUCCESS = "success", "Réussi"
        FAILED = "failed", "Échoué"
        REVERSED = "reversed", "Annulé"

    member = models.ForeignKey("memberships.Member", on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    provider = models.CharField(max_length=32, choices=Provider.choices, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.INITIATED, db_index=True)
    phone = models.CharField(max_length=32, blank=True, db_index=True)
    external_reference = models.CharField(max_length=120, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=120, unique=True)
    purpose = models.CharField(max_length=80, db_index=True)
    provider_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["mutuelle", "provider", "status"])]
