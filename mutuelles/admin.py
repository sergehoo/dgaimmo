from django.contrib import admin

from mutuelles.models import Mutuelle, MutuelleMembership


@admin.register(Mutuelle)
class MutuelleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization_name",
        "organization_type",
        "real_estate_objectives_display",
        "estimated_members_count",
        "country",
        "currency",
        "status",
        "subscription_plan",
        "created_at",
    )
    list_filter = (
        "country",
        "status",
        "subscription_plan",
        "organization_type",
        # real_estate_objective est désormais une liste JSON :
        # un list_filter natif n'est plus possible, le filtre se fait via
        # la recherche/JSON. On peut ajouter un SimpleListFilter dédié plus tard.
    )
    search_fields = (
        "name",
        "legal_name",
        "organization_name",
        "slug",
        "custom_domain",
        "contact_last_name",
        "contact_first_name",
        "contact_email",
    )
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Identité", {
            "fields": ("name", "slug", "legal_name", "status"),
        }),
        ("Organisation porteuse", {
            "fields": ("organization_name", "organization_type", "estimated_members_count"),
        }),
        ("Objectif immobilier", {
            "fields": ("real_estate_objective", "real_estate_objective_details"),
        }),
        ("Contact référent", {
            "fields": (
                "contact_last_name",
                "contact_first_name",
                "contact_function",
                "contact_email",
                "contact_phone",
            ),
        }),
        ("Localisation & SaaS", {
            "fields": (
                "country",
                "currency",
                "subscription_plan",
                "custom_domain",
                "headquarters_location",
            ),
        }),
        ("Branding", {
            "fields": ("logo", "primary_color", "accent_color"),
        }),
        ("Configuration avancée", {
            "classes": ("collapse",),
            "fields": ("business_rules", "settings"),
        }),
    )


@admin.register(MutuelleMembership)
class MutuelleMembershipAdmin(admin.ModelAdmin):
    list_display = ("mutuelle", "user", "role", "active", "created_at")
    list_filter = ("role", "active")
    search_fields = ("mutuelle__name", "user__email")
