from core.serializers import TenantModelSerializer
from real_estate.models import (
    BankLoanOffer,
    BankPartner,
    CollectiveFinancingPlan,
    DebtCommitment,
    DeveloperProfile,
    FinancingScenario,
    MemberCreditScore,
    MemberFinancialProfile,
    MortgageApplication,
    MutuelleGlobalScore,
    MutuelleLoanOffer,
    ProgramRiskAnalysis,
    PropertyDocument,
    PropertyLot,
    PropertyReservation,
    QuotiteCessibleSimulation,
    RealEstateOpportunity,
    RealEstateProgram,
    RealEstateProgramScore,
)


class DeveloperProfileSerializer(TenantModelSerializer):
    class Meta:
        model = DeveloperProfile
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class RealEstateProgramSerializer(TenantModelSerializer):
    class Meta:
        model = RealEstateProgram
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class RealEstateOpportunitySerializer(TenantModelSerializer):
    class Meta:
        model = RealEstateOpportunity
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class PropertyLotSerializer(TenantModelSerializer):
    class Meta:
        model = PropertyLot
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class PropertyReservationSerializer(TenantModelSerializer):
    class Meta:
        model = PropertyReservation
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class PropertyDocumentSerializer(TenantModelSerializer):
    class Meta:
        model = PropertyDocument
        fields = "__all__"
        read_only_fields = ["mutuelle", "ocr_payload", "verified"]


class MemberFinancialProfileSerializer(TenantModelSerializer):
    class Meta:
        model = MemberFinancialProfile
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class DebtCommitmentSerializer(TenantModelSerializer):
    class Meta:
        model = DebtCommitment
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class QuotiteCessibleSimulationSerializer(TenantModelSerializer):
    class Meta:
        model = QuotiteCessibleSimulation
        fields = "__all__"
        read_only_fields = [
            "mutuelle",
            "total_income",
            "monthly_charges",
            "existing_debt_payments",
            "gross_capacity",
            "net_capacity",
            "max_authorized_payment",
            "estimated_payment",
            "debt_ratio",
            "living_remainder",
            "financeable_amount",
            "decision",
            "recommendations",
        ]


class FinancingScenarioSerializer(TenantModelSerializer):
    class Meta:
        model = FinancingScenario
        fields = "__all__"
        read_only_fields = ["mutuelle", "monthly_payment", "total_cost", "repayment_plan"]


class BankPartnerSerializer(TenantModelSerializer):
    class Meta:
        model = BankPartner
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class MortgageApplicationSerializer(TenantModelSerializer):
    class Meta:
        model = MortgageApplication
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class MemberCreditScoreSerializer(TenantModelSerializer):
    class Meta:
        model = MemberCreditScore
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class MutuelleGlobalScoreSerializer(TenantModelSerializer):
    class Meta:
        model = MutuelleGlobalScore
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class RealEstateProgramScoreSerializer(TenantModelSerializer):
    class Meta:
        model = RealEstateProgramScore
        fields = "__all__"
        read_only_fields = ["mutuelle"]
