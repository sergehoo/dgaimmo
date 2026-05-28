from django.contrib import admin

from memberships.models import Bank, Beneficiary, KYCDocument, Member


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country", "is_partner", "active", "created_at")
    list_filter = ("country", "is_partner", "active")
    search_fields = ("name", "code")
    list_editable = ("is_partner", "active")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "member_code",
        "last_name",
        "first_name",
        "phone",
        "mutuelle",
        "employer",
        "job_function",
        "marital_status",
        "bank",
        "status",
        "kyc_validated",
    )
    list_filter = (
        "status",
        "kyc_validated",
        "marital_status",
        "bank",
        "mutuelle",
    )
    search_fields = (
        "member_code",
        "first_name",
        "last_name",
        "phone",
        "email",
        "national_id",
        "employer",
        "job_function",
    )
    autocomplete_fields = ("bank",)
    fieldsets = (
        ("Identité", {
            "fields": (
                "mutuelle",
                "member_code",
                "user",
                "first_name",
                "last_name",
                "gender",
                "birth_date",
                "birth_place",
                "national_id",
                "photo",
                "qr_token",
            ),
        }),
        ("Contact", {
            "fields": ("phone", "email", "location"),
        }),
        ("Situation familiale", {
            "fields": ("marital_status", "spouse_name", "dependents_count"),
        }),
        ("Vie professionnelle", {
            "fields": (
                "employer",
                "job_function",
                "hire_date",
                "professional_seniority_months",
            ),
        }),
        ("Banque affiliée", {
            "fields": ("bank", "bank_account_number"),
        }),
        ("Statut & KYC", {
            "fields": ("status", "joined_at", "kyc_validated", "metadata"),
        }),
    )


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "relationship", "member", "mutuelle")
    search_fields = ("full_name", "member__first_name", "member__last_name")


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ("member", "document_type", "verified", "created_at")
    list_filter = ("document_type", "verified")
