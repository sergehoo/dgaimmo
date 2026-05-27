from django.db import models

from core.models import TenantModel


class GeneralAssembly(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        SCHEDULED = "scheduled", "Planifiée"
        LIVE = "live", "En cours"
        CLOSED = "closed", "Clôturée"

    title = models.CharField(max_length=180, db_index=True)
    scheduled_at = models.DateTimeField(db_index=True)
    location = models.CharField(max_length=180, blank=True)
    online_url = models.URLField(blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    quorum_required = models.PositiveSmallIntegerField(default=50)
    minutes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_at"]
        indexes = [models.Index(fields=["mutuelle", "status", "scheduled_at"])]

    def __str__(self):
        return self.title


class Resolution(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        OPEN = "open", "Vote ouvert"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Rejetée"

    assembly = models.ForeignKey(GeneralAssembly, on_delete=models.CASCADE, related_name="resolutions")
    title = models.CharField(max_length=180, db_index=True)
    description = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    approval_threshold = models.PositiveSmallIntegerField(default=50)
    closes_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["mutuelle", "status"])]

    def __str__(self):
        return self.title


class ResolutionVote(TenantModel):
    class Choice(models.TextChoices):
        YES = "yes", "Pour"
        NO = "no", "Contre"
        ABSTAIN = "abstain", "Abstention"

    resolution = models.ForeignKey(Resolution, on_delete=models.CASCADE, related_name="votes")
    member = models.ForeignKey("memberships.Member", on_delete=models.CASCADE, related_name="governance_votes")
    choice = models.CharField(max_length=16, choices=Choice.choices, db_index=True)
    signed_hash = models.CharField(max_length=128, blank=True, db_index=True)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["resolution", "member"], name="unique_resolution_member_vote")]
        indexes = [models.Index(fields=["mutuelle", "choice", "voted_at"])]


class ElectronicSignature(TenantModel):
    class SignatureType(models.TextChoices):
        ATTENDANCE = "attendance", "Présence AG"
        RESOLUTION = "resolution", "Résolution"
        CONTRACT = "contract", "Contrat"

    member = models.ForeignKey("memberships.Member", on_delete=models.CASCADE, related_name="electronic_signatures")
    signature_type = models.CharField(max_length=24, choices=SignatureType.choices, db_index=True)
    related_object_type = models.CharField(max_length=120, blank=True)
    related_object_id = models.CharField(max_length=120, blank=True)
    signature_hash = models.CharField(max_length=128, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_fingerprint = models.CharField(max_length=180, blank=True)

    class Meta:
        indexes = [models.Index(fields=["mutuelle", "signature_type", "created_at"])]
