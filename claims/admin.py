from django.contrib import admin

from claims.models import AssistanceClaim, ClaimDocument


@admin.register(AssistanceClaim)
class AssistanceClaimAdmin(admin.ModelAdmin):
    list_display = ("member", "claim_type", "status", "amount", "approved_amount", "created_at")
    list_filter = ("claim_type", "status", "mutuelle")
    search_fields = ("member__first_name", "member__last_name", "beneficiary_name", "description")


@admin.register(ClaimDocument)
class ClaimDocumentAdmin(admin.ModelAdmin):
    list_display = ("claim", "document_type", "verified", "created_at")
    list_filter = ("document_type", "verified", "mutuelle")
    search_fields = ("claim__member__first_name", "claim__member__last_name", "document_type")
