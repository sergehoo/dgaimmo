from rest_framework import viewsets

from contributions.models import Contribution, ContributionPlan
from contributions.serializers import ContributionPlanSerializer, ContributionSerializer


class ContributionPlanViewSet(viewsets.ModelViewSet):
    queryset = ContributionPlan.objects.all()
    serializer_class = ContributionPlanSerializer
    filterset_fields = ["frequency", "active"]
    search_fields = ["name"]
    ordering_fields = ["created_at", "amount"]


class ContributionViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.select_related("member", "plan", "mutuelle")
    serializer_class = ContributionSerializer
    search_fields = ["member__first_name", "member__last_name", "receipt_number"]
    filterset_fields = ["status", "due_date", "currency"]
    ordering_fields = ["due_date", "created_at", "amount"]
