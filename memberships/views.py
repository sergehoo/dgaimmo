from rest_framework import decorators, response, viewsets

from core.permissions import IsMandataire
from memberships.models import Member
from memberships.serializers import MemberSerializer


class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.select_related("mutuelle", "user")
    serializer_class = MemberSerializer
    permission_classes = [IsMandataire]
    search_fields = ["member_code", "first_name", "last_name", "phone", "national_id"]
    filterset_fields = ["status", "kyc_validated"]
    ordering_fields = ["created_at", "joined_at", "last_name"]

    @decorators.action(detail=True, methods=["get"], url_path="digital-card")
    def digital_card(self, request, pk=None):
        member = self.get_object()
        return response.Response(
            {
                "member_code": member.member_code,
                "full_name": str(member),
                "status": member.status,
                "qr_token": member.qr_token,
                "kyc_validated": member.kyc_validated,
            }
        )
