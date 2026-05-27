from core.serializers import TenantModelSerializer
from ai_engine.models import AIAnalysis


class AIAnalysisSerializer(TenantModelSerializer):
    class Meta:
        model = AIAnalysis
        fields = "__all__"
        read_only_fields = ["mutuelle", "result", "confidence"]
