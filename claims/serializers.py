from claims.models import AssistanceClaim, ClaimDocument
from core.serializers import TenantModelSerializer


class AssistanceClaimSerializer(TenantModelSerializer):
    class Meta:
        model = AssistanceClaim
        fields = "__all__"
        read_only_fields = ["mutuelle", "paid_at"]


class ClaimDocumentSerializer(TenantModelSerializer):
    class Meta:
        model = ClaimDocument
        fields = "__all__"
        read_only_fields = ["mutuelle", "ocr_payload"]
