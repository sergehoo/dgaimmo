from core.serializers import TenantModelSerializer
from treasury.models import CashAccount, LedgerEntry


class CashAccountSerializer(TenantModelSerializer):
    class Meta:
        model = CashAccount
        fields = "__all__"
        read_only_fields = ["mutuelle"]


class LedgerEntrySerializer(TenantModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = "__all__"
        read_only_fields = ["mutuelle"]
