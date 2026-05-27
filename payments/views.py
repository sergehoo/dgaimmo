from rest_framework import decorators, response, status, viewsets
from rest_framework.permissions import AllowAny

from payments.models import Payment
from payments.serializers import PaymentSerializer
from payments.services import initiate_mobile_money_payment, process_mobile_money_webhook


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("member", "mutuelle")
    serializer_class = PaymentSerializer
    filterset_fields = ["provider", "status", "purpose"]
    search_fields = ["phone", "external_reference", "idempotency_key"]

    def get_permissions(self):
        if self.action == "mobile_money_webhook":
            return [AllowAny()]
        return super().get_permissions()

    @decorators.action(detail=False, methods=["post"], url_path="mobile-money/initiate")
    def mobile_money_initiate(self, request):
        payment = initiate_mobile_money_payment(request.mutuelle, request.data)
        return response.Response(PaymentSerializer(payment, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=["post"], url_path="mobile-money/webhook")
    def mobile_money_webhook(self, request):
        payment = process_mobile_money_webhook(request.data)
        return response.Response({"status": "processed", "payment": str(payment.id), "payment_status": payment.status})

    @decorators.action(detail=True, methods=["post"], url_path="simulate-success")
    def simulate_success(self, request, pk=None):
        payment = self.get_object()
        payment = process_mobile_money_webhook({"reference": payment.external_reference, "status": "success", "source": "manual_simulation"})
        return response.Response(PaymentSerializer(payment, context={"request": request}).data)
