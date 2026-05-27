from django.contrib import admin

from governance.models import ElectronicSignature, GeneralAssembly, Resolution, ResolutionVote


@admin.register(GeneralAssembly)
class GeneralAssemblyAdmin(admin.ModelAdmin):
    list_display = ("title", "mutuelle", "scheduled_at", "status", "quorum_required")
    list_filter = ("status", "mutuelle")
    search_fields = ("title", "location")


@admin.register(Resolution)
class ResolutionAdmin(admin.ModelAdmin):
    list_display = ("title", "assembly", "status", "approval_threshold")
    list_filter = ("status", "mutuelle")
    search_fields = ("title", "description")


@admin.register(ResolutionVote)
class ResolutionVoteAdmin(admin.ModelAdmin):
    list_display = ("resolution", "member", "choice", "voted_at")
    list_filter = ("choice", "mutuelle")
    search_fields = ("resolution__title", "member__first_name", "member__last_name")


@admin.register(ElectronicSignature)
class ElectronicSignatureAdmin(admin.ModelAdmin):
    list_display = ("member", "signature_type", "related_object_type", "created_at")
    list_filter = ("signature_type", "mutuelle")
    search_fields = ("member__first_name", "member__last_name", "signature_hash")
