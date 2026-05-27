from django.contrib import admin

from core.models import AuditTrail, TenantQuota


@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ("action", "resource_type", "mutuelle", "actor", "ip_address", "created_at")
    list_filter = ("action", "resource_type", "mutuelle")
    search_fields = ("resource_id", "user_agent")


@admin.register(TenantQuota)
class TenantQuotaAdmin(admin.ModelAdmin):
    list_display = ("mutuelle", "max_members", "max_storage_mb", "max_monthly_ai_calls", "max_mandataires")
