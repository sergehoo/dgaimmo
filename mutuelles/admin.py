from django.contrib import admin

from mutuelles.models import Mutuelle, MutuelleMembership


@admin.register(Mutuelle)
class MutuelleAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "currency", "status", "subscription_plan", "created_at")
    list_filter = ("country", "status", "subscription_plan")
    search_fields = ("name", "legal_name", "slug", "custom_domain")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(MutuelleMembership)
class MutuelleMembershipAdmin(admin.ModelAdmin):
    list_display = ("mutuelle", "user", "role", "active", "created_at")
    list_filter = ("role", "active")
    search_fields = ("mutuelle__name", "user__email")
