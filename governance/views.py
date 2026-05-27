import hashlib
import uuid

from rest_framework import decorators, response, viewsets

from governance.models import ElectronicSignature, GeneralAssembly, Resolution, ResolutionVote
from governance.serializers import (
    ElectronicSignatureSerializer,
    GeneralAssemblySerializer,
    ResolutionSerializer,
    ResolutionVoteSerializer,
)


class GeneralAssemblyViewSet(viewsets.ModelViewSet):
    queryset = GeneralAssembly.objects.all()
    serializer_class = GeneralAssemblySerializer
    filterset_fields = ["status"]
    search_fields = ["title", "location"]


class ResolutionViewSet(viewsets.ModelViewSet):
    queryset = Resolution.objects.select_related("assembly")
    serializer_class = ResolutionSerializer
    filterset_fields = ["status", "assembly"]
    search_fields = ["title", "description"]

    @decorators.action(detail=True, methods=["get"], url_path="results")
    def results(self, request, pk=None):
        resolution = self.get_object()
        votes = resolution.votes.all()
        total = votes.count()
        yes = votes.filter(choice=ResolutionVote.Choice.YES).count()
        no = votes.filter(choice=ResolutionVote.Choice.NO).count()
        abstain = votes.filter(choice=ResolutionVote.Choice.ABSTAIN).count()
        approved = total > 0 and (yes / total) * 100 >= resolution.approval_threshold
        return response.Response({"total": total, "yes": yes, "no": no, "abstain": abstain, "approved": approved})


class ResolutionVoteViewSet(viewsets.ModelViewSet):
    queryset = ResolutionVote.objects.select_related("resolution", "member")
    serializer_class = ResolutionVoteSerializer
    filterset_fields = ["choice", "resolution", "member"]

    def perform_create(self, serializer):
        resolution = serializer.validated_data["resolution"]
        member = serializer.validated_data["member"]
        payload = f"{resolution.id}:{member.id}:{serializer.validated_data['choice']}:{uuid.uuid4().hex}"
        serializer.save(mutuelle=resolution.mutuelle, signed_hash=hashlib.sha256(payload.encode()).hexdigest())


class ElectronicSignatureViewSet(viewsets.ModelViewSet):
    queryset = ElectronicSignature.objects.select_related("member")
    serializer_class = ElectronicSignatureSerializer
    filterset_fields = ["signature_type", "member"]

    def perform_create(self, serializer):
        member = serializer.validated_data["member"]
        payload = f"{member.id}:{serializer.validated_data['signature_type']}:{uuid.uuid4().hex}"
        serializer.save(mutuelle=member.mutuelle, signature_hash=hashlib.sha256(payload.encode()).hexdigest())
