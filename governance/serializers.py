from core.serializers import TenantModelSerializer
from governance.models import ElectronicSignature, GeneralAssembly, Resolution, ResolutionVote


class GeneralAssemblySerializer(TenantModelSerializer):
    class Meta:
        model = GeneralAssembly
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class ResolutionSerializer(TenantModelSerializer):
    class Meta:
        model = Resolution
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class ResolutionVoteSerializer(TenantModelSerializer):
    class Meta:
        model = ResolutionVote
        fields = "__all__"
        read_only_fields = ["mutuelle", "signed_hash", "voted_at"]


class ElectronicSignatureSerializer(TenantModelSerializer):
    class Meta:
        model = ElectronicSignature
        fields = "__all__"
        read_only_fields = ["mutuelle", "signature_hash"]
