from rest_framework import viewsets

from core.permissions import IsMutuelleAdmin
from mutuelles.models import Mutuelle
from mutuelles.serializers import MutuelleSerializer


class MutuelleViewSet(viewsets.ModelViewSet):
    queryset = Mutuelle.objects.all()
    serializer_class = MutuelleSerializer
    permission_classes = [IsMutuelleAdmin]
    search_fields = ["name", "legal_name", "slug"]
    ordering_fields = ["created_at", "name", "status"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Mutuelle.objects.all()
        return Mutuelle.objects.filter(id=self.request.user.default_mutuelle_id)
