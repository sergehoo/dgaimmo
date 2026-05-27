from django.http import JsonResponse

from core.models import AuditTrail
from core.tenant import set_active_mutuelle
from mutuelles.models import Mutuelle


class ActiveTenantMiddleware:
    """Resolve active tenant from header, subdomain placeholder, or user's default mutuelle."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        mutuelle_id = request.headers.get("X-Mutuelle-ID")
        request.mutuelle = None
        if mutuelle_id:
            request.mutuelle = Mutuelle.objects.filter(id=mutuelle_id).first()
        elif getattr(request, "user", None) and request.user.is_authenticated:
            request.mutuelle = request.user.default_mutuelle

        set_active_mutuelle(request.mutuelle.id if request.mutuelle else None)
        response = self.get_response(request)
        set_active_mutuelle(None)
        return response


class SecurityAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/") and response.status_code in {401, 403, 429}:
            AuditTrail.objects.create(
                mutuelle=getattr(request, "mutuelle", None),
                actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                action=f"security.http_{response.status_code}",
                resource_type="http_request",
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                metadata={"path": request.path, "method": request.method},
            )
        return response
