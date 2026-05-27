from rest_framework import decorators, response, viewsets

from ai_engine.models import AIAnalysis
from ai_engine.serializers import AIAnalysisSerializer
from ai_engine.services import analyze_real_estate_opportunity
from real_estate.models import RealEstateOpportunity


class AIAnalysisViewSet(viewsets.ModelViewSet):
    queryset = AIAnalysis.objects.all()
    serializer_class = AIAnalysisSerializer
    filterset_fields = ["analysis_type", "provider"]
    search_fields = ["prompt", "related_object_type", "related_object_id"]

    @decorators.action(detail=False, methods=["post"], url_path="real-estate-opportunity")
    def real_estate_opportunity(self, request):
        opportunity = RealEstateOpportunity.objects.get(id=request.data["opportunity"])
        result = analyze_real_estate_opportunity(opportunity)
        analysis = AIAnalysis.all_objects.create(
            mutuelle=request.mutuelle,
            analysis_type="real_estate_opportunity",
            provider=result["provider"],
            prompt=f"Analyse programme immobilier: {opportunity.title}",
            result=result,
            confidence=72,
            related_object_type="RealEstateOpportunity",
            related_object_id=str(opportunity.id),
        )
        return response.Response(AIAnalysisSerializer(analysis, context={"request": request}).data)
