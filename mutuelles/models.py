from django.db import models

from core.fields import geo_point_field
from core.models import TimeStampedModel


class Mutuelle(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PENDING = "pending", "En validation"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspendue"

    name = models.CharField(max_length=180, db_index=True)
    slug = models.SlugField(unique=True)
    legal_name = models.CharField(max_length=180, blank=True)
    country = models.CharField(max_length=2, default="CI", db_index=True)
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    logo = models.ImageField(upload_to="mutuelles/logos/", blank=True, null=True)
    primary_color = models.CharField(max_length=16, default="#0f766e")
    accent_color = models.CharField(max_length=16, default="#f59e0b")
    subscription_plan = models.CharField(max_length=60, default="starter", db_index=True)
    custom_domain = models.CharField(max_length=180, blank=True, db_index=True)
    headquarters_location = geo_point_field(null=True)
    business_rules = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["country", "status"]),
            models.Index(fields=["subscription_plan", "status"]),
        ]

    def __str__(self):
        return self.name


class MutuelleMembership(TimeStampedModel):
    mutuelle = models.ForeignKey(Mutuelle, on_delete=models.CASCADE, related_name="staff_memberships")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="mutuelle_memberships")
    role = models.CharField(max_length=32, db_index=True)
    permissions = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("mutuelle", "user")]
        indexes = [models.Index(fields=["mutuelle", "role", "active"])]
