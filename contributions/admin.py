from django.contrib import admin

from contributions.models import Contribution, ContributionPlan


@admin.register(ContributionPlan)
class ContributionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "mutuelle", "frequency", "amount", "active")
    list_filter = ("frequency", "active", "mutuelle")
    search_fields = ("name",)


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("member", "plan", "amount", "currency", "status", "due_date", "paid_at")
    list_filter = ("status", "currency", "due_date", "mutuelle")
    search_fields = ("member__first_name", "member__last_name", "receipt_number")
