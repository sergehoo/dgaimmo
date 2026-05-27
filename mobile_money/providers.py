import uuid


SUPPORTED_PROVIDERS = {"orange_money", "mtn_money", "wave", "moov_money"}


class MobileMoneyProviderError(ValueError):
    pass


def build_collection_intent(provider, payment):
    if provider not in SUPPORTED_PROVIDERS:
        raise MobileMoneyProviderError(f"Unsupported Mobile Money provider: {provider}")
    reference = payment.external_reference or f"MM-{provider[:3].upper()}-{uuid.uuid4().hex[:12].upper()}"
    return {
        "provider": provider,
        "reference": reference,
        "status": "pending",
        "checkout_url": f"https://pay.dga-imo360.local/{provider}/{reference}",
        "instructions": "Confirmez le paiement sur le téléphone du membre.",
    }
