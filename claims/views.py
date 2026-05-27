from rest_framework import decorators, response, viewsets

from claims.models import AssistanceClaim, ClaimDocument
from claims.serializers import AssistanceClaimSerializer, ClaimDocumentSerializer
from claims.services import advance_claim


class AssistanceClaimViewSet(viewsets.ModelViewSet):
    queryset = AssistanceClaim.objects.select_related("member", "mutuelle")
    serializer_class = AssistanceClaimSerializer
    filterset_fields = ["status", "claim_type", "member"]
    search_fields = ["member__first_name", "member__last_name", "beneficiary_name", "description"]
    ordering_fields = ["created_at", "amount", "approved_amount", "incident_date"]

    def perform_create(self, serializer):
        member = serializer.validated_data["member"]
        serializer.save(mutuelle=member.mutuelle)

    @decorators.action(detail=True, methods=["post"], url_path="advance")
    def advance(self, request, pk=None):
        claim = advance_claim(self.get_object())
        return response.Response(AssistanceClaimSerializer(claim, context={"request": request}).data)


class ClaimDocumentViewSet(viewsets.ModelViewSet):
    queryset = ClaimDocument.objects.select_related("claim", "mutuelle")
    serializer_class = ClaimDocumentSerializer
    filterset_fields = ["claim", "document_type", "verified"]
    search_fields = ["document_type", "claim__member__first_name", "claim__member__last_name"]

    def perform_create(self, serializer):
        claim = serializer.validated_data["claim"]
        serializer.save(mutuelle=claim.mutuelle, ocr_payload={"status": "queued", "engine": "hybrid_ocr"})
