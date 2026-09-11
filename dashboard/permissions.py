"""Résolution du rôle applicatif d'un utilisateur.

Le modèle ``accounts.User`` a un champ ``role`` (superadmin, mutuelle_admin,
member, mandataire) mais la source de vérité opérationnelle est
``mutuelles.MutuelleMembership`` (rattachement + rôle par tenant). Ce
module réconcilie les deux et expose un rôle applicatif unique + helpers
de routing.

Rôles applicatifs :
- ``superadmin``     : ``user.is_superuser`` (voit toutes les mutuelles)
- ``mutuelle_admin`` : au moins une MutuelleMembership active avec role ≠ ``member``
- ``mutualiste``     : profil Member existant (et pas d'admin actif)
- ``invite``         : invitation MemberInvitation en attente sans Member
- ``anonymous``      : non authentifié
"""

from __future__ import annotations


ROLE_SUPERADMIN = "superadmin"
ROLE_MUTUELLE_ADMIN = "mutuelle_admin"
ROLE_MUTUALISTE = "mutualiste"
ROLE_INVITE = "invite"
ROLE_ANONYMOUS = "anonymous"

ROLE_LABELS = {
    ROLE_SUPERADMIN: "Super administrateur",
    ROLE_MUTUELLE_ADMIN: "Administrateur mutuelle",
    ROLE_MUTUALISTE: "Mutualiste",
    ROLE_INVITE: "Invité",
    ROLE_ANONYMOUS: "Anonyme",
}


def resolve_role(user) -> str:
    """Retourne le rôle applicatif unique d'un utilisateur."""
    if user is None or not getattr(user, "is_authenticated", False):
        return ROLE_ANONYMOUS

    if user.is_superuser:
        return ROLE_SUPERADMIN

    # Imports paresseux pour éviter les imports circulaires
    from memberships.models import Member, MemberInvitation
    from mutuelles.models import MutuelleMembership

    is_admin_of_a_mutuelle = (
        MutuelleMembership.objects.filter(user=user, active=True)
        .exclude(role="member")
        .exists()
    )
    if is_admin_of_a_mutuelle:
        return ROLE_MUTUELLE_ADMIN

    has_member_profile = Member.all_objects.filter(user=user).exists()
    if has_member_profile:
        return ROLE_MUTUALISTE

    email = (getattr(user, "email", "") or "").strip().lower()
    if email:
        pending_invite = MemberInvitation.all_objects.filter(
            email=email,
            status__in=[MemberInvitation.Status.PENDING, MemberInvitation.Status.SENT],
        ).exists()
        if pending_invite:
            return ROLE_INVITE

    # Fallback : utilisateur connecté sans rattachement métier → invite muet
    return ROLE_INVITE


def resolve_home_url_name(role: str) -> str:
    """URL cible par défaut pour chaque rôle (utilisée par LOGIN_REDIRECT)."""
    return {
        ROLE_SUPERADMIN: "platform-center",
        ROLE_MUTUELLE_ADMIN: "dashboard-home",
        ROLE_MUTUALISTE: "member-portal",
        ROLE_INVITE: "invite-landing",
        ROLE_ANONYMOUS: "login",
    }.get(role, "dashboard-home")


def is_staff_role(role: str) -> bool:
    """True si le rôle donne accès au back-office console."""
    return role in {ROLE_SUPERADMIN, ROLE_MUTUELLE_ADMIN}


def role_context_processor(request):
    """Injecte ``user_role`` et ``user_role_label`` dans tous les templates."""
    role = resolve_role(getattr(request, "user", None))
    return {
        "user_role": role,
        "user_role_label": ROLE_LABELS.get(role, ""),
        "is_superadmin": role == ROLE_SUPERADMIN,
        "is_mutuelle_admin": role == ROLE_MUTUELLE_ADMIN,
        "is_mutualiste": role == ROLE_MUTUALISTE,
        "is_invite": role == ROLE_INVITE,
    }
