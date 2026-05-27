from django.contrib import admin

from payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("provider", "status", "purpose", "member", "amount", "currency", "created_at")
    list_filter = ("provider", "status", "purpose", "currency")
    search_fields = ("phone", "external_reference", "idempotency_key", "member__first_name", "member__last_name")
