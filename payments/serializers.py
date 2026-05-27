from core.serializers import TenantModelSerializer
from payments.models import Payment


class PaymentSerializer(TenantModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["mutuelle", "provider_payload"]
