from django.contrib import admin

from real_estate.models import (
    BankPartner,
    CollectiveFinancingPlan,
    DebtCommitment,
    DeveloperProfile,
    FinancingScenario,
    MemberCreditScore,
    MemberFinancialProfile,
    MortgageApplication,
    MutuelleGlobalScore,
    PropertyDocument,
    PropertyLot,
    PropertyReservation,
    QuotiteCessibleSimulation,
    RealEstateOpportunity,
    RealEstateProgram,
    RealEstateProgramScore,
)


@admin.register(RealEstateProgram)
class RealEstateProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "mutuelle", "city", "country", "total_lots", "status")
    list_filter = ("status", "city", "country", "mutuelle")
    search_fields = ("name", "description", "city")


@admin.register(RealEstateOpportunity)
class RealEstateOpportunityAdmin(admin.ModelAdmin):
    list_display = ("title", "program", "property_type", "amount", "currency", "available_lots", "status", "score")
    list_filter = ("property_type", "status", "currency")
    search_fields = ("title", "program__name", "location_label")


@admin.register(PropertyLot)
class PropertyLotAdmin(admin.ModelAdmin):
    list_display = ("lot_number", "opportunity", "amount", "currency", "status", "assigned_member")
    list_filter = ("status", "currency")
    search_fields = ("lot_number", "opportunity__title", "assigned_member__first_name", "assigned_member__last_name")


@admin.register(PropertyReservation)
class PropertyReservationAdmin(admin.ModelAdmin):
    list_display = ("lot", "member", "status", "deposit_paid", "reserved_until")
    list_filter = ("status",)
    search_fields = ("lot__lot_number", "member__first_name", "member__last_name")


@admin.register(MemberFinancialProfile)
class MemberFinancialProfileAdmin(admin.ModelAdmin):
    list_display = ("member", "employment_type", "net_monthly_salary", "complementary_income", "risk_level")
    list_filter = ("employment_type", "risk_level")
    search_fields = ("member__first_name", "member__last_name", "member__phone")


@admin.register(QuotiteCessibleSimulation)
class QuotiteCessibleSimulationAdmin(admin.ModelAdmin):
    list_display = ("member", "requested_amount", "estimated_payment", "debt_ratio", "living_remainder", "decision", "created_at")
    list_filter = ("decision",)
    search_fields = ("member__first_name", "member__last_name")


@admin.register(FinancingScenario)
class FinancingScenarioAdmin(admin.ModelAdmin):
    list_display = ("member", "opportunity", "mode", "principal", "monthly_payment", "total_cost")
    list_filter = ("mode",)
    search_fields = ("member__first_name", "member__last_name", "opportunity__title")


admin.site.register(DeveloperProfile)
admin.site.register(DebtCommitment)
admin.site.register(MemberCreditScore)
admin.site.register(MutuelleGlobalScore)
admin.site.register(RealEstateProgramScore)
admin.site.register(MortgageApplication)
admin.site.register(BankPartner)
admin.site.register(CollectiveFinancingPlan)
admin.site.register(PropertyDocument)
