from django.contrib import admin

from memberships.models import Beneficiary, KYCDocument, Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("member_code", "first_name", "last_name", "phone", "mutuelle", "status", "kyc_validated")
    list_filter = ("status", "kyc_validated", "mutuelle")
    search_fields = ("member_code", "first_name", "last_name", "phone", "national_id")


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "relationship", "member", "mutuelle")
    search_fields = ("full_name", "member__first_name", "member__last_name")


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ("member", "document_type", "verified", "created_at")
    list_filter = ("document_type", "verified")
