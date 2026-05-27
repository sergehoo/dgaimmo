import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from accounts.models import LoginEvent, OTPChallenge, UserDevice


def _hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()


def request_meta(request):
    return {
        "ip_address": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "device_id": request.COOKIES.get("dga_device_id") or request.headers.get("X-Device-ID", ""),
    }


def record_login_event(request, status, user=None, email="", metadata=None):
    meta = request_meta(request)
    return LoginEvent.objects.create(
        user=user,
        email=email or getattr(user, "email", ""),
        status=status,
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
        device_id=meta["device_id"],
        metadata=metadata or {},
    )


def upsert_user_device(request, user, trusted=False):
    meta = request_meta(request)
    device_id = meta["device_id"] or secrets.token_urlsafe(24)
    device, _ = UserDevice.objects.update_or_create(
        user=user,
        device_id=device_id,
        defaults={
            "name": "Navigateur web",
            "trusted": trusted,
            "last_ip": meta["ip_address"],
            "last_seen_at": timezone.now(),
        },
    )
    return device


def create_otp_challenge(user, purpose=OTPChallenge.Purpose.LOGIN, channel="email"):
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = OTPChallenge.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash_code(code),
        expires_at=timezone.now() + timedelta(minutes=10),
        delivery_channel=channel,
        delivery_target=user.email if channel == "email" else user.phone or user.email,
    )
    return challenge, code


def verify_otp_challenge(challenge, code):
    if challenge.status != OTPChallenge.Status.PENDING:
        return False
    if challenge.is_expired:
        challenge.status = OTPChallenge.Status.EXPIRED
        challenge.save(update_fields=["status"])
        return False
    challenge.attempts += 1
    if challenge.code_hash == _hash_code(code):
        challenge.status = OTPChallenge.Status.VERIFIED
        challenge.verified_at = timezone.now()
        challenge.save(update_fields=["attempts", "status", "verified_at"])
        return True
    if challenge.attempts >= 5:
        challenge.status = OTPChallenge.Status.FAILED
    challenge.save(update_fields=["attempts", "status"])
    return False
