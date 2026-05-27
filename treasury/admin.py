from django.contrib import admin

from treasury.models import CashAccount, LedgerEntry


@admin.register(CashAccount)
class CashAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "mutuelle", "account_type", "balance", "currency", "active")
    list_filter = ("account_type", "active", "currency")
    search_fields = ("name",)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("cash_account", "direction", "category", "amount", "currency", "occurred_at")
    list_filter = ("direction", "category", "currency", "mutuelle")
    search_fields = ("reference", "description")
