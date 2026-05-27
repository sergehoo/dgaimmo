from core.serializers import TenantModelSerializer
from contributions.models import Contribution, ContributionPlan


class ContributionPlanSerializer(TenantModelSerializer):
    class Meta:
        model = ContributionPlan
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class ContributionSerializer(TenantModelSerializer):
    class Meta:
        model = Contribution
        fields = "__all__"
        read_only_fields = ["mutuelle"]
