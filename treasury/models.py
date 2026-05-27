from django.db import models

from core.models import MoneyModel, TenantModel


class CashAccount(TenantModel):
    class AccountType(models.TextChoices):
        MAIN = "main", "Caisse principale"
        AGENCY = "agency", "Caisse agence"
        BANK = "bank", "Compte bancaire"
        MOBILE_MONEY = "mobile_money", "Mobile Money"

    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=32, choices=AccountType.choices, db_index=True)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="XOF")
    active = models.BooleanField(default=True, db_index=True)


class LedgerEntry(TenantModel, MoneyModel):
    class Direction(models.TextChoices):
        CREDIT = "credit", "Crédit"
        DEBIT = "debit", "Débit"

    cash_account = models.ForeignKey(CashAccount, on_delete=models.PROTECT, related_name="entries")
    direction = models.CharField(max_length=12, choices=Direction.choices, db_index=True)
    category = models.CharField(max_length=80, db_index=True)
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["mutuelle", "direction", "occurred_at"])]
