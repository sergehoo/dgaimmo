from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsTenantMember(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return bool(getattr(request, "mutuelle", None) or getattr(request.user, "default_mutuelle_id", None))

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        obj_mutuelle_id = getattr(obj, "mutuelle_id", None)
        if obj_mutuelle_id is None:
            return request.method in SAFE_METHODS
        active_id = getattr(getattr(request, "mutuelle", None), "id", None) or request.user.default_mutuelle_id
        return obj_mutuelle_id == active_id


class IsMutuelleAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in {"superadmin", "mutuelle_admin"})


class IsMandataire(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in {"superadmin", "mutuelle_admin", "mandataire"})
