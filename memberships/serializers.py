from core.serializers import TenantModelSerializer
from memberships.models import Beneficiary, KYCDocument, Member


class MemberSerializer(TenantModelSerializer):
    class Meta:
        model = Member
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class BeneficiarySerializer(TenantModelSerializer):
    class Meta:
        model = Beneficiary
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class KYCDocumentSerializer(TenantModelSerializer):
    class Meta:
        model = KYCDocument
        fields = "__all__"
        read_only_fields = ["mutuelle", "ocr_payload"]
