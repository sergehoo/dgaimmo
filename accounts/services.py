import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import LoginEvent, OTPChallenge, UserDevice

logger = logging.getLogger("mutuellex.accounts")


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


# -----------------------------------------------------------------------------
# Emails transactionnels
# -----------------------------------------------------------------------------
def _resolve_app_url(request=None, path: str = "/") -> str:
    """Retourne une URL absolue vers l'app, tolère l'absence de request."""
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            pass
    domain = getattr(settings, "APP_DOMAIN", None) or "localhost:8000"
    protocol = "https" if getattr(settings, "SECURE_SSL_REDIRECT", False) else "http"
    return f"{protocol}://{domain}{path}"


def send_welcome_email(user, mutuelle=None, request=None) -> bool:
    """Email de bienvenue à l'inscription (mutualiste OU admin mutuelle).

    Retourne True si l'envoi a réussi, False sinon (l'appel ne bloque jamais
    l'inscription — un email raté ne doit pas casser le workflow).
    """
    if not user or not user.email:
        return False
    login_url = _resolve_app_url(request, reverse("login"))
    dashboard_url = _resolve_app_url(request, reverse("dashboard-home"))
    ctx = {
        "user": user,
        "first_name": (user.first_name or "").strip() or user.email,
        "last_name": (user.last_name or "").strip(),
        "mutuelle": mutuelle,
        "mutuelle_name": mutuelle.name if mutuelle is not None else "",
        "login_url": login_url,
        "dashboard_url": dashboard_url,
        "app_domain": getattr(settings, "APP_DOMAIN", "") or "DGA Mutuelle",
    }
    subject = "Bienvenue sur DGA Mutuelle"
    if mutuelle is not None:
        subject = f"Bienvenue sur DGA Mutuelle — {mutuelle.name}"
    body_text = render_to_string("emails/welcome.txt", ctx)
    body_html = render_to_string("emails/welcome.html", ctx)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@dgamutuelle.com"
    try:
        send_mail(
            subject=subject,
            message=body_text,
            html_message=body_html,
            from_email=from_email,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Échec envoi email de bienvenue à %s", user.email, exc_info=True)
        return False
