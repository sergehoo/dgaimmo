from rest_framework import viewsets

from treasury.models import CashAccount, LedgerEntry
from treasury.serializers import CashAccountSerializer, LedgerEntrySerializer


class CashAccountViewSet(viewsets.ModelViewSet):
    queryset = CashAccount.objects.all()
    serializer_class = CashAccountSerializer
    filterset_fields = ["account_type", "active"]
    search_fields = ["name"]


class LedgerEntryViewSet(viewsets.ModelViewSet):
    queryset = LedgerEntry.objects.select_related("cash_account")
    serializer_class = LedgerEntrySerializer
    filterset_fields = ["direction", "category", "currency"]
    search_fields = ["reference", "description"]
    ordering_fields = ["occurred_at", "amount"]
