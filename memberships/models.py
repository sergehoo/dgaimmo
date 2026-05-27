from django.db import models

from core.fields import geo_point_field
from core.models import TenantModel


class Member(TenantModel):
    class Status(models.TextChoices):
        PROSPECT = "prospect", "Prospect"
        ACTIVE = "active", "Actif"
        DELINQUENT = "delinquent", "En retard"
        SUSPENDED = "suspended", "Suspendu"

    user = models.OneToOneField("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="member_profile")
    member_code = models.CharField(max_length=40, db_index=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32, db_index=True)
    email = models.EmailField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    national_id = models.CharField(max_length=80, blank=True, db_index=True)
    photo = models.ImageField(upload_to="members/photos/", null=True, blank=True)
    qr_token = models.CharField(max_length=120, unique=True, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PROSPECT, db_index=True)
    joined_at = models.DateField(null=True, blank=True, db_index=True)
    location = geo_point_field(null=True)
    kyc_validated = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("mutuelle", "member_code")]
        indexes = [
            models.Index(fields=["mutuelle", "status"]),
            models.Index(fields=["mutuelle", "phone"]),
            models.Index(fields=["mutuelle", "kyc_validated"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Beneficiary(TenantModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="beneficiaries")
    full_name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=60)
    birth_date = models.DateField(null=True, blank=True)
    kyc_document = models.FileField(upload_to="beneficiaries/kyc/", null=True, blank=True)


class KYCDocument(TenantModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="kyc_documents")
    document_type = models.CharField(max_length=80, db_index=True)
    file = models.FileField(upload_to="members/kyc/")
    verified = models.BooleanField(default=False, db_index=True)
    ocr_payload = models.JSONField(default=dict, blank=True)
