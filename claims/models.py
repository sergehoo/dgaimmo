from django.db import models

from core.models import MoneyModel, TenantModel


class AssistanceClaim(TenantModel, MoneyModel):
    class ClaimType(models.TextChoices):
        ILLNESS = "illness", "Maladie"
        DEATH = "death", "Décès"
        ACCIDENT = "accident", "Accident"
        MATERNITY = "maternity", "Maternité"
        MARRIAGE = "marriage", "Mariage"
        DISASTER = "disaster", "Catastrophe"
        EDUCATION = "education", "Aide scolaire"

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        SUBMITTED = "submitted", "Demandée"
        REVIEW = "review", "Analyse"
        APPROVED = "approved", "Approuvée"
        PAID = "paid", "Payée"
        CLOSED = "closed", "Clôturée"
        REJECTED = "rejected", "Rejetée"

    member = models.ForeignKey("memberships.Member", on_delete=models.PROTECT, related_name="assistance_claims")
    claim_type = models.CharField(max_length=32, choices=ClaimType.choices, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    beneficiary_name = models.CharField(max_length=180, blank=True)
    incident_date = models.DateField(null=True, blank=True, db_index=True)
    description = models.TextField()
    approved_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    decision_notes = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["mutuelle", "status", "claim_type"]),
            models.Index(fields=["member", "status"]),
        ]


class ClaimDocument(TenantModel):
    claim = models.ForeignKey(AssistanceClaim, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=80, db_index=True)
    file = models.FileField(upload_to="claims/documents/")
    verified = models.BooleanField(default=False, db_index=True)
    ocr_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["mutuelle", "document_type", "verified"])]
