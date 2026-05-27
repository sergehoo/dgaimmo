from rest_framework import decorators, response, serializers, status, viewsets

from memberships.models import Member
from real_estate.models import (
    BankPartner,
    FinancingScenario,
    MemberFinancialProfile,
    MortgageApplication,
    PropertyDocument,
    PropertyLot,
    PropertyReservation,
    QuotiteCessibleSimulation,
    RealEstateOpportunity,
    RealEstateProgram,
)
from real_estate.serializers import (
    BankPartnerSerializer,
    FinancingScenarioSerializer,
    MemberFinancialProfileSerializer,
    MortgageApplicationSerializer,
    PropertyDocumentSerializer,
    PropertyLotSerializer,
    PropertyReservationSerializer,
    QuotiteCessibleSimulationSerializer,
    RealEstateOpportunitySerializer,
    RealEstateProgramSerializer,
)
from real_estate.services import (
    compute_member_score,
    compute_mutuelle_score,
    compute_program_score,
    create_financing_scenario,
    simulate_quotite,
)
from real_estate.tasks import process_property_document_ocr


class RealEstateScoreActionSerializer(serializers.Serializer):
    member = serializers.UUIDField(required=False)


class RealEstateProgramViewSet(viewsets.ModelViewSet):
    queryset = RealEstateProgram.objects.select_related("developer")
    serializer_class = RealEstateProgramSerializer
    filterset_fields = ["status", "city", "country"]
    search_fields = ["name", "description", "city"]
    ordering_fields = ["created_at", "delivery_deadline", "total_lots"]

    @decorators.action(detail=True, methods=["post"], url_path="score")
    def score(self, request, pk=None):
        score = compute_program_score(request.mutuelle, self.get_object())
        return response.Response({"score": score.score, "risk_level": score.risk_level, "recommendation": score.recommendation})


class RealEstateOpportunityViewSet(viewsets.ModelViewSet):
    queryset = RealEstateOpportunity.objects.select_related("program")
    serializer_class = RealEstateOpportunitySerializer
    filterset_fields = ["property_type", "status", "currency"]
    search_fields = ["title", "location_label", "program__name"]
    ordering_fields = ["amount", "score", "created_at", "available_lots"]

    @decorators.action(detail=True, methods=["post"], url_path="simulate-financing")
    def simulate_financing(self, request, pk=None):
        member = Member.objects.get(id=request.data["member"])
        scenario = create_financing_scenario(
            request.mutuelle,
            member,
            self.get_object(),
            request.data.get("mode", FinancingScenario.Mode.MUTUELLE_LOAN),
            request.data.get("personal_deposit", 0),
            request.data.get("duration_months", 120),
            request.data.get("annual_interest_rate", 8),
        )
        return response.Response(FinancingScenarioSerializer(scenario, context={"request": request}).data, status=status.HTTP_201_CREATED)


class PropertyLotViewSet(viewsets.ModelViewSet):
    queryset = PropertyLot.objects.select_related("opportunity", "assigned_member")
    serializer_class = PropertyLotSerializer
    filterset_fields = ["status", "opportunity"]
    search_fields = ["lot_number", "assigned_member__first_name", "assigned_member__last_name"]


class PropertyReservationViewSet(viewsets.ModelViewSet):
    queryset = PropertyReservation.objects.select_related("lot", "member")
    serializer_class = PropertyReservationSerializer
    filterset_fields = ["status", "member", "lot"]
    search_fields = ["member__first_name", "member__last_name", "lot__lot_number"]

    def perform_create(self, serializer):
        reservation = serializer.save(mutuelle=self.request.mutuelle)
        reservation.lot.status = PropertyLot.Status.RESERVED
        reservation.lot.save(update_fields=["status"])


class PropertyDocumentViewSet(viewsets.ModelViewSet):
    queryset = PropertyDocument.objects.select_related("program", "mutuelle")
    serializer_class = PropertyDocumentSerializer
    filterset_fields = ["program", "document_type", "verified"]
    search_fields = ["document_type", "program__name"]

    def perform_create(self, serializer):
        program = serializer.validated_data["program"]
        serializer.save(mutuelle=program.mutuelle, ocr_payload={"status": "queued", "engine": "hybrid_ocr"})

    @decorators.action(detail=True, methods=["post"], url_path="process-ocr")
    def process_ocr(self, request, pk=None):
        payload = process_property_document_ocr(str(self.get_object().id))
        return response.Response(payload)


class QuotiteCessibleSimulationViewSet(viewsets.ModelViewSet):
    queryset = QuotiteCessibleSimulation.objects.select_related("member")
    serializer_class = QuotiteCessibleSimulationSerializer
    filterset_fields = ["decision", "member"]
    ordering_fields = ["created_at", "debt_ratio", "financeable_amount"]

    def create(self, request, *args, **kwargs):
        member = Member.objects.get(id=request.data["member"])
        simulation = simulate_quotite(
            request.mutuelle,
            member,
            request.data.get("requested_amount", 0),
            request.data.get("requested_duration_months", 120),
            request.data.get("annual_interest_rate", 8),
            request.data.get("max_debt_ratio", 33),
        )
        return response.Response(self.get_serializer(simulation).data, status=status.HTTP_201_CREATED)


class FinancingScenarioViewSet(viewsets.ModelViewSet):
    queryset = FinancingScenario.objects.select_related("member", "opportunity")
    serializer_class = FinancingScenarioSerializer
    filterset_fields = ["mode", "member", "opportunity"]
    ordering_fields = ["monthly_payment", "total_cost", "created_at"]


class MemberFinancialProfileViewSet(viewsets.ModelViewSet):
    queryset = MemberFinancialProfile.objects.select_related("member")
    serializer_class = MemberFinancialProfileSerializer
    filterset_fields = ["employment_type", "risk_level", "member"]
    search_fields = ["member__first_name", "member__last_name", "member__phone"]


class MortgageApplicationViewSet(viewsets.ModelViewSet):
    queryset = MortgageApplication.objects.select_related("member", "scenario")
    serializer_class = MortgageApplicationSerializer
    filterset_fields = ["status", "member"]
    search_fields = ["bank_reference", "member__first_name", "member__last_name"]


class BankPartnerViewSet(viewsets.ModelViewSet):
    queryset = BankPartner.objects.all()
    serializer_class = BankPartnerSerializer
    filterset_fields = ["country", "active"]
    search_fields = ["name"]


class RealEstateScoreViewSet(viewsets.ViewSet):
    serializer_class = RealEstateScoreActionSerializer

    @decorators.action(detail=False, methods=["post"], url_path="member")
    def member(self, request):
        score = compute_member_score(request.mutuelle, Member.objects.get(id=request.data["member"]))
        return response.Response({"score": score.score, "level": score.level, "risk": score.default_risk, "recommendations": score.recommendations})

    @decorators.action(detail=False, methods=["post"], url_path="mutuelle")
    def mutuelle(self, request):
        score = compute_mutuelle_score(request.mutuelle)
        return response.Response(
            {
                "score": score.score,
                "health_level": score.health_level,
                "max_collective_financing": score.max_collective_financing,
                "risk_level": score.risk_level,
                "metrics": score.metrics,
            }
        )

    @decorators.action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        opportunities = RealEstateOpportunity.objects.filter(status=RealEstateOpportunity.Status.AVAILABLE)
        simulations = QuotiteCessibleSimulation.objects.all().order_by("-created_at")[:10]
        return response.Response(
            {
                "available_opportunities": opportunities.count(),
                "programs_in_progress": RealEstateProgram.objects.filter(status__in=["review", "active", "approved"]).count(),
                "recent_simulations": QuotiteCessibleSimulationSerializer(simulations, many=True).data,
                "collective_capacity": compute_mutuelle_score(request.mutuelle).max_collective_financing,
            }
        )
