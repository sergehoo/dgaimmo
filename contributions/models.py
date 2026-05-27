from django.db import models

from core.models import MoneyModel, TenantModel


class ContributionPlan(TenantModel):
    class Frequency(models.TextChoices):
        MONTHLY = "monthly", "Mensuelle"
        YEARLY = "yearly", "Annuelle"
        EXCEPTIONAL = "exceptional", "Exceptionnelle"

    name = models.CharField(max_length=120)
    frequency = models.CharField(max_length=24, choices=Frequency.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    penalty_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    active = models.BooleanField(default=True, db_index=True)


class Contribution(TenantModel, MoneyModel):
    class Status(models.TextChoices):
        DUE = "due", "Due"
        PARTIAL = "partial", "Partielle"
        PAID = "paid", "Payée"
        OVERDUE = "overdue", "En retard"

    member = models.ForeignKey("memberships.Member", on_delete=models.PROTECT, related_name="contributions")
    plan = models.ForeignKey(ContributionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateField(db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DUE, db_index=True)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receipt_number = models.CharField(max_length=80, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["mutuelle", "status", "due_date"]),
            models.Index(fields=["member", "status"]),
        ]
