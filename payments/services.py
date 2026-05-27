import uuid

from django.db import transaction
from django.utils import timezone

from contributions.models import Contribution
from mobile_money.providers import build_collection_intent
from payments.models import Payment
from treasury.models import CashAccount, LedgerEntry


def initiate_mobile_money_payment(mutuelle, payload):
    idempotency_key = payload.get("idempotency_key") or str(uuid.uuid4())
    existing = Payment.all_objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    contribution = None
    if payload.get("contribution"):
        contribution = Contribution.all_objects.select_related("member").get(id=payload["contribution"], mutuelle=mutuelle)
    member = contribution.member if contribution else payload.get("member")
    payment = Payment.all_objects.create(
        mutuelle=mutuelle,
        provider=payload["provider"],
        member=member if hasattr(member, "id") else None,
        phone=payload.get("phone", getattr(member, "phone", "")),
        amount=payload.get("amount", contribution.amount if contribution else 0),
        currency=payload.get("currency", mutuelle.currency),
        purpose=payload.get("purpose", "contribution"),
        idempotency_key=idempotency_key,
        status=Payment.Status.PENDING,
        provider_payload={
            "intent": "collect",
            "channel": payload["provider"],
            "contribution_id": str(contribution.id) if contribution else payload.get("contribution_id", ""),
        },
    )
    intent = build_collection_intent(payment.provider, payment)
    payment.external_reference = intent["reference"]
    payment.provider_payload = {**payment.provider_payload, **intent}
    payment.save(update_fields=["external_reference", "provider_payload", "updated_at"])
    return payment


@transaction.atomic
def process_mobile_money_webhook(payload):
    reference = payload.get("reference") or payload.get("external_reference")
    idempotency_key = payload.get("idempotency_key")
    payment = None
    if reference:
        payment = Payment.all_objects.select_for_update().filter(external_reference=reference).first()
    if not payment and idempotency_key:
        payment = Payment.all_objects.select_for_update().filter(idempotency_key=idempotency_key).first()
    if not payment:
        raise Payment.DoesNotExist("Payment not found for webhook payload")

    provider_status = payload.get("status", "").lower()
    if provider_status in {"success", "succeeded", "paid"}:
        payment.status = Payment.Status.SUCCESS
    elif provider_status in {"failed", "error", "expired"}:
        payment.status = Payment.Status.FAILED
    else:
        payment.status = Payment.Status.PENDING

    payment.provider_payload = {
        **payment.provider_payload,
        "webhook": payload,
        "webhook_processed_at": timezone.now().isoformat(),
    }
    payment.save(update_fields=["status", "provider_payload", "updated_at"])

    if payment.status == Payment.Status.SUCCESS:
        _apply_successful_payment(payment)
    return payment


def _apply_successful_payment(payment):
    contribution_id = payment.provider_payload.get("contribution_id")
    contribution = None
    if contribution_id:
        contribution = Contribution.all_objects.select_for_update().filter(id=contribution_id, mutuelle=payment.mutuelle).first()
    if contribution and contribution.status != Contribution.Status.PAID:
        contribution.status = Contribution.Status.PAID
        contribution.paid_at = timezone.now()
        if not contribution.receipt_number:
            contribution.receipt_number = f"RCT-{uuid.uuid4().hex[:10].upper()}"
        contribution.save(update_fields=["status", "paid_at", "receipt_number", "updated_at"])

    cash_account, _ = CashAccount.all_objects.get_or_create(
        mutuelle=payment.mutuelle,
        name=f"Caisse {payment.get_provider_display()}",
        defaults={
            "account_type": CashAccount.AccountType.MOBILE_MONEY,
            "balance": 0,
            "currency": payment.currency,
            "active": True,
        },
    )
    cash_account.balance += payment.amount
    cash_account.save(update_fields=["balance", "updated_at"])
    LedgerEntry.all_objects.get_or_create(
        mutuelle=payment.mutuelle,
        cash_account=cash_account,
        reference=payment.external_reference,
        defaults={
            "direction": LedgerEntry.Direction.CREDIT,
            "category": "mobile_money_collection",
            "amount": payment.amount,
            "currency": payment.currency,
            "description": f"Encaissement {payment.get_provider_display()}",
            "occurred_at": timezone.now(),
            "metadata": {"payment_id": str(payment.id), "contribution_id": contribution_id or ""},
        },
    )
