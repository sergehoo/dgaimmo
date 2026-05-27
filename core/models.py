import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.tenant import get_active_mutuelle_id


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantQuerySet(models.QuerySet):
    def for_active_tenant(self):
        mutuelle_id = get_active_mutuelle_id()
        if mutuelle_id:
            return self.filter(mutuelle_id=mutuelle_id)
        return self


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db).for_active_tenant()

    def all_tenants(self):
        return TenantQuerySet(self.model, using=self._db)


class TenantModel(TimeStampedModel):
    mutuelle = models.ForeignKey("mutuelles.Mutuelle", on_delete=models.PROTECT, related_name="%(class)ss")

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["mutuelle", "created_at"])]


class MoneyModel(models.Model):
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="XOF", db_index=True)

    class Meta:
        abstract = True


class AuditTrail(TimeStampedModel):
    mutuelle = models.ForeignKey("mutuelles.Mutuelle", on_delete=models.SET_NULL, null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=120, db_index=True)
    resource_type = models.CharField(max_length=120, db_index=True)
    resource_id = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["mutuelle", "action", "created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]


class TenantQuota(TimeStampedModel):
    mutuelle = models.OneToOneField("mutuelles.Mutuelle", on_delete=models.CASCADE, related_name="quota")
    max_members = models.PositiveIntegerField(default=500)
    max_storage_mb = models.PositiveIntegerField(default=1024)
    max_monthly_ai_calls = models.PositiveIntegerField(default=1000)
    max_mandataires = models.PositiveIntegerField(default=25)
    current_storage_mb = models.PositiveIntegerField(default=0)
    current_monthly_ai_calls = models.PositiveIntegerField(default=0)
    reset_at = models.DateTimeField(default=timezone.now)

    def can_add_member(self, current_member_count: int) -> bool:
        return current_member_count < self.max_members
