from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", "SuperAdmin"
        MUTUELLE_ADMIN = "mutuelle_admin", "Admin Mutuelle"
        MEMBER = "member", "Mutualiste"
        MANDATAIRE = "mandataire", "Mandataire"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, unique=True, null=True, blank=True, db_index=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.MEMBER, db_index=True)
    default_mutuelle = models.ForeignKey(
        "mutuelles.Mutuelle", on_delete=models.SET_NULL, null=True, blank=True, related_name="default_users"
    )
    mfa_enabled = models.BooleanField(default=False)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_seen_device = models.CharField(max_length=255, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]


class UserDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    device_id = models.CharField(max_length=120, db_index=True)
    name = models.CharField(max_length=120, blank=True)
    trusted = models.BooleanField(default=False)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "device_id")]


class OTPChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = "login", "Connexion"
        SENSITIVE_ACTION = "sensitive_action", "Action sensible"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        VERIFIED = "verified", "Vérifié"
        EXPIRED = "expired", "Expiré"
        FAILED = "failed", "Échoué"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_challenges")
    purpose = models.CharField(max_length=32, choices=Purpose.choices, default=Purpose.LOGIN, db_index=True)
    code_hash = models.CharField(max_length=128)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    delivery_channel = models.CharField(max_length=24, default="email")
    delivery_target = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class LoginEvent(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Succès"
        FAILED = "failed", "Échec"
        LOCKED = "locked", "Verrouillé"
        MFA_REQUIRED = "mfa_required", "MFA requis"

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_events")
    email = models.EmailField(blank=True, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_id = models.CharField(max_length=120, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email", "status", "created_at"])]
