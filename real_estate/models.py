from django.db import models

from core.fields import geo_point_field
from core.models import MoneyModel, TenantModel, TimeStampedModel


class DeveloperProfile(TenantModel):
    name = models.CharField(max_length=180, db_index=True)
    legal_status = models.CharField(max_length=120, blank=True)
    registration_number = models.CharField(max_length=120, blank=True, db_index=True)
    track_record = models.JSONField(default=dict, blank=True)
    contact = models.JSONField(default=dict, blank=True)
    risk_notes = models.TextField(blank=True)


class RealEstateProgram(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        REVIEW = "review", "Analyse"
        APPROVED = "approved", "Approuvé"
        ACTIVE = "active", "Actif"
        DELIVERED = "delivered", "Livré"
        REJECTED = "rejected", "Rejeté"

    name = models.CharField(max_length=180, db_index=True)
    developer = models.ForeignKey(DeveloperProfile, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    location = geo_point_field(null=True)
    city = models.CharField(max_length=120, blank=True, db_index=True)
    country = models.CharField(max_length=2, default="CI", db_index=True)
    total_lots = models.PositiveIntegerField(default=0)
    delivery_deadline = models.DateField(null=True, blank=True)
    legal_status = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    documents_checklist = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["mutuelle", "status", "city"])]


class RealEstateOpportunity(TenantModel, MoneyModel):
    class PropertyType(models.TextChoices):
        LAND = "land", "Terrain"
        VILLA = "villa", "Villa"
        APARTMENT = "apartment", "Appartement"
        SOCIAL_HOUSING = "social_housing", "Logement social"
        DEVELOPER_PROGRAM = "developer_program", "Programme promoteur"
        COLLECTIVE_BUILD = "collective_build", "Construction collective"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        RESERVED = "reserved", "Réservée"
        SOLD_OUT = "sold_out", "Épuisée"
        PAUSED = "paused", "Suspendue"

    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="opportunities")
    title = models.CharField(max_length=180, db_index=True)
    property_type = models.CharField(max_length=32, choices=PropertyType.choices, db_index=True)
    location_label = models.CharField(max_length=180, blank=True)
    initial_deposit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    financing_months = models.PositiveIntegerField(default=120)
    estimated_monthly_payment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ancillary_fees = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    available_lots = models.PositiveIntegerField(default=0)
    interested_members_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict, blank=True)


class PropertyLot(TenantModel, MoneyModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        RESERVED = "reserved", "Réservé"
        ASSIGNED = "assigned", "Affecté"
        DELIVERED = "delivered", "Livré"

    opportunity = models.ForeignKey(RealEstateOpportunity, on_delete=models.CASCADE, related_name="lots")
    lot_number = models.CharField(max_length=80, db_index=True)
    surface_area = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    assigned_member = models.ForeignKey("memberships.Member", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = [("mutuelle", "opportunity", "lot_number")]


class PropertyReservation(TenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvée"
        CANCELLED = "cancelled", "Annulée"
        CONVERTED = "converted", "Convertie"

    lot = models.ForeignKey(PropertyLot, on_delete=models.PROTECT, related_name="reservations")
    member = models.ForeignKey("memberships.Member", on_delete=models.PROTECT, related_name="property_reservations")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    reserved_until = models.DateTimeField(null=True, blank=True)
    deposit_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    decision_notes = models.TextField(blank=True)


class MemberFinancialProfile(TenantModel):
    class EmploymentType(models.TextChoices):
        PUBLIC = "public", "Fonctionnaire"
        PRIVATE = "private", "Salarié privé"
        INDEPENDENT = "independent", "Indépendant"
        INFORMAL = "informal", "Revenus informels"

    member = models.OneToOneField("memberships.Member", on_delete=models.CASCADE, related_name="financial_profile")
    net_monthly_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    complementary_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    fixed_charges = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pensions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    mutual_contributions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    dependents_count = models.PositiveSmallIntegerField(default=0)
    professional_seniority_months = models.PositiveIntegerField(default=0)
    contract_type = models.CharField(max_length=80, blank=True)
    employment_type = models.CharField(max_length=24, choices=EmploymentType.choices, default=EmploymentType.PRIVATE)
    risk_level = models.CharField(max_length=24, default="medium", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    @property
    def total_income(self):
        return self.net_monthly_salary + self.complementary_income + self.pensions


class DebtCommitment(TenantModel):
    member = models.ForeignKey("memberships.Member", on_delete=models.CASCADE, related_name="debt_commitments")
    lender = models.CharField(max_length=160)
    monthly_payment = models.DecimalField(max_digits=14, decimal_places=2)
    outstanding_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ends_at = models.DateField(null=True, blank=True)
    verified = models.BooleanField(default=False, db_index=True)


class QuotiteCessibleSimulation(TenantModel):
    class Decision(models.TextChoices):
        ELIGIBLE = "eligible", "Éligible"
        CONDITIONAL = "conditional", "Éligible sous réserve"
        REJECTED = "rejected", "Non éligible"

    member = models.ForeignKey("memberships.Member", on_delete=models.PROTECT, related_name="quotite_simulations")
    requested_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    requested_duration_months = models.PositiveIntegerField(default=120)
    annual_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=8)
    max_debt_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=33)
    total_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monthly_charges = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    existing_debt_payments = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_capacity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_capacity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    max_authorized_payment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estimated_payment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    debt_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    living_remainder = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    financeable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    decision = models.CharField(max_length=24, choices=Decision.choices, default=Decision.CONDITIONAL, db_index=True)
    recommendations = models.JSONField(default=list, blank=True)


class MemberCreditScore(TenantModel):
    member = models.OneToOneField("memberships.Member", on_delete=models.CASCADE, related_name="credit_score")
    score = models.PositiveSmallIntegerField(default=0, db_index=True)
    level = models.CharField(max_length=24, db_index=True)
    default_risk = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_recommended_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    recommendations = models.JSONField(default=list, blank=True)
    factors = models.JSONField(default=dict, blank=True)


class MutuelleGlobalScore(TenantModel):
    score = models.PositiveSmallIntegerField(default=0, db_index=True)
    health_level = models.CharField(max_length=24, db_index=True)
    max_collective_financing = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    max_bank_guarantee = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    risk_level = models.CharField(max_length=24, default="medium", db_index=True)
    recommendations = models.JSONField(default=list, blank=True)
    metrics = models.JSONField(default=dict, blank=True)


class RealEstateProgramScore(TenantModel):
    program = models.OneToOneField(RealEstateProgram, on_delete=models.CASCADE, related_name="program_score")
    score = models.PositiveSmallIntegerField(default=0, db_index=True)
    risk_level = models.CharField(max_length=24, db_index=True)
    recommendation = models.CharField(max_length=24, db_index=True)
    ai_summary = models.TextField(blank=True)
    checklist = models.JSONField(default=dict, blank=True)
    factors = models.JSONField(default=dict, blank=True)


class FinancingScenario(TenantModel):
    class Mode(models.TextChoices):
        MUTUELLE_LOAN = "mutuelle_loan", "Prêt mutuelle"
        BANK_LOAN = "bank_loan", "Prêt bancaire"
        MIXED = "mixed", "Mutuelle + banque"
        PROGRESSIVE_SAVINGS = "progressive_savings", "Épargne progressive"
        PERSONAL_MUTUELLE = "personal_mutuelle", "Apport + mutuelle"
        PERSONAL_BANK = "personal_bank", "Apport + banque"

    member = models.ForeignKey("memberships.Member", on_delete=models.PROTECT, related_name="financing_scenarios")
    opportunity = models.ForeignKey(RealEstateOpportunity, on_delete=models.PROTECT, related_name="financing_scenarios")
    mode = models.CharField(max_length=32, choices=Mode.choices, db_index=True)
    property_price = models.DecimalField(max_digits=14, decimal_places=2)
    personal_deposit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    principal = models.DecimalField(max_digits=14, decimal_places=2)
    annual_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=8)
    duration_months = models.PositiveIntegerField(default=120)
    monthly_payment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    repayment_plan = models.JSONField(default=list, blank=True)


class BankPartner(TenantModel):
    name = models.CharField(max_length=180, db_index=True)
    country = models.CharField(max_length=2, default="CI", db_index=True)
    contact = models.JSONField(default=dict, blank=True)
    min_rate = models.DecimalField(max_digits=5, decimal_places=2, default=7)
    max_duration_months = models.PositiveIntegerField(default=240)
    active = models.BooleanField(default=True, db_index=True)


class BankLoanOffer(TenantModel):
    bank = models.ForeignKey(BankPartner, on_delete=models.PROTECT, related_name="loan_offers")
    scenario = models.ForeignKey(FinancingScenario, on_delete=models.CASCADE, related_name="bank_offers")
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=14, decimal_places=2)
    duration_months = models.PositiveIntegerField()
    conditions = models.JSONField(default=dict, blank=True)


class MutuelleLoanOffer(TenantModel):
    scenario = models.ForeignKey(FinancingScenario, on_delete=models.CASCADE, related_name="mutuelle_offers")
    approved_amount = models.DecimalField(max_digits=14, decimal_places=2)
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    duration_months = models.PositiveIntegerField()
    guarantee_required = models.DecimalField(max_digits=14, decimal_places=2, default=0)


class MortgageApplication(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        COMMITTEE = "committee", "Comité"
        BANK_REVIEW = "bank_review", "Banque"
        APPROVED = "approved", "Approuvé"
        DISBURSED = "disbursed", "Décaissé"
        CLOSED = "closed", "Clôturé"
        REJECTED = "rejected", "Rejeté"

    member = models.ForeignKey("memberships.Member", on_delete=models.PROTECT, related_name="mortgage_applications")
    scenario = models.ForeignKey(FinancingScenario, on_delete=models.PROTECT, related_name="applications")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT, db_index=True)
    committee_notes = models.TextField(blank=True)
    bank_reference = models.CharField(max_length=120, blank=True, db_index=True)
    disbursed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)


class CollectiveFinancingPlan(TenantModel):
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="collective_plans")
    target_amount = models.DecimalField(max_digits=16, decimal_places=2)
    mobilizable_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    member_count = models.PositiveIntegerField(default=0)
    risk_summary = models.JSONField(default=dict, blank=True)
    projection = models.JSONField(default=list, blank=True)


class PropertyDocument(TenantModel):
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="property_documents")
    document_type = models.CharField(max_length=80, db_index=True)
    file = models.FileField(upload_to="real_estate/documents/")
    verified = models.BooleanField(default=False, db_index=True)
    ocr_payload = models.JSONField(default=dict, blank=True)


class ProgramRiskAnalysis(TenantModel):
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="risk_analyses")
    analyst = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    risk_level = models.CharField(max_length=24, db_index=True)
    findings = models.JSONField(default=list, blank=True)
    ai_summary = models.TextField(blank=True)
