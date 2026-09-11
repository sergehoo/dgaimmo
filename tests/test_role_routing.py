"""Tests role-based routing.

Vérifie que chaque type d'utilisateur (superadmin, admin mutuelle,
mutualiste, invité) est redirigé vers la bonne vue au login et voit un
menu adapté à son rôle.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dashboard.permissions import (
    ROLE_INVITE,
    ROLE_MUTUALISTE,
    ROLE_MUTUELLE_ADMIN,
    ROLE_SUPERADMIN,
    resolve_role,
)
from memberships.models import Member, MemberInvitation
from mutuelles.models import Mutuelle, MutuelleMembership


User = get_user_model()

TEST_OVERRIDES = dict(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)


@override_settings(**TEST_OVERRIDES)
class RoleResolverTests(TestCase):
    def setUp(self):
        self.mutuelle = Mutuelle.objects.create(
            name="Mutuelle Alpha", slug="mutuelle-alpha",
            organization_name="Alpha SARL",
            organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10, country="CI", currency="XOF",
        )

    def test_superadmin_role(self):
        u = User.objects.create_superuser(
            username="root@x.ci", email="root@x.ci", password="P@ssw0rd!12345",
        )
        self.assertEqual(resolve_role(u), ROLE_SUPERADMIN)

    def test_mutuelle_admin_role(self):
        u = User.objects.create_user(
            username="admin@x.ci", email="admin@x.ci", password="P@ssw0rd!12345",
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle, user=u, role="admin", permissions=["*"], active=True,
        )
        self.assertEqual(resolve_role(u), ROLE_MUTUELLE_ADMIN)

    def test_mutualiste_role(self):
        u = User.objects.create_user(
            username="marie@x.ci", email="marie@x.ci", password="P@ssw0rd!12345",
        )
        Member.all_objects.create(
            mutuelle=self.mutuelle, user=u,
            member_code="MA-2026-0001",
            first_name="Marie", last_name="MEMBRE",
            phone="+2250700111100", email="marie@x.ci",
            qr_token="qr-marie-2",
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle, user=u, role="member", permissions=[], active=True,
        )
        self.assertEqual(resolve_role(u), ROLE_MUTUALISTE)

    def test_invite_role(self):
        # User connecté avec invitation en attente pour son email, sans profil membre
        u = User.objects.create_user(
            username="prospect@x.ci", email="prospect@x.ci", password="P@ssw0rd!12345",
        )
        MemberInvitation.all_objects.create(
            mutuelle=self.mutuelle, email="prospect@x.ci",
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.assertEqual(resolve_role(u), ROLE_INVITE)


@override_settings(**TEST_OVERRIDES)
class LoginRoutingTests(TestCase):
    def setUp(self):
        self.password = "P@ssw0rd!12345"
        self.mutuelle = Mutuelle.objects.create(
            name="Mutuelle Route", slug="mutuelle-route",
            organization_name="Route SARL",
            organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10, country="CI", currency="XOF",
        )

    def _post_login(self, email):
        return self.client.post(
            reverse("login"),
            {"username": email, "password": self.password},
            follow=False,
        )

    def test_superadmin_redirects_to_platform(self):
        User.objects.create_superuser(
            username="root@rt.ci", email="root@rt.ci", password=self.password,
        )
        resp = self._post_login("root@rt.ci")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("platform-center"), resp.url)

    def test_admin_redirects_to_console_dashboard(self):
        u = User.objects.create_user(
            username="admin@rt.ci", email="admin@rt.ci", password=self.password,
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle, user=u, role="admin", permissions=["*"], active=True,
        )
        resp = self._post_login("admin@rt.ci")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("dashboard-home"), resp.url)

    def test_mutualiste_redirects_to_member_portal(self):
        u = User.objects.create_user(
            username="marie@rt.ci", email="marie@rt.ci", password=self.password,
        )
        Member.all_objects.create(
            mutuelle=self.mutuelle, user=u,
            member_code="MR-2026-0001", first_name="Marie", last_name="RT",
            phone="+2250700222200", email="marie@rt.ci",
            qr_token="qr-marie-3",
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle, user=u, role="member", permissions=[], active=True,
        )
        resp = self._post_login("marie@rt.ci")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("member-portal"), resp.url)

    def test_invite_redirects_to_invite_landing(self):
        User.objects.create_user(
            username="prospect@rt.ci", email="prospect@rt.ci", password=self.password,
        )
        MemberInvitation.all_objects.create(
            mutuelle=self.mutuelle, email="prospect@rt.ci",
            expires_at=timezone.now() + timedelta(days=7),
        )
        resp = self._post_login("prospect@rt.ci")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("invite-landing"), resp.url)


@override_settings(**TEST_OVERRIDES)
class RoleScopedViewsTests(TestCase):
    def setUp(self):
        self.password = "P@ssw0rd!12345"
        self.mutuelle_a = Mutuelle.objects.create(
            name="Mut A", slug="mut-a",
            organization_name="A SARL",
            organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10, country="CI", currency="XOF",
        )
        self.mutuelle_b = Mutuelle.objects.create(
            name="Mut B", slug="mut-b",
            organization_name="B SARL",
            organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10, country="CI", currency="XOF",
        )

    def test_platform_center_only_superadmin(self):
        # Admin mutuelle → redirigé
        admin = User.objects.create_user(
            username="adm@sc.ci", email="adm@sc.ci", password=self.password,
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle_a, user=admin, role="admin", permissions=["*"], active=True,
        )
        self.client.login(username="adm@sc.ci", password=self.password)
        resp = self.client.get(reverse("platform-center"))
        self.assertEqual(resp.status_code, 302)  # redirect vers dashboard-home
        self.client.logout()

        # Superadmin → 200
        root = User.objects.create_superuser(
            username="root@sc.ci", email="root@sc.ci", password=self.password,
        )
        self.client.login(username="root@sc.ci", password=self.password)
        resp = self.client.get(reverse("platform-center"))
        self.assertEqual(resp.status_code, 200)
        # Voit les deux mutuelles
        self.assertContains(resp, "Mut A")
        self.assertContains(resp, "Mut B")

    def test_admin_mutuelle_list_redirects_to_own_detail(self):
        """Un admin avec une seule mutuelle est redirigé vers son détail
        (pas de liste 'toutes les mutuelles')."""
        u = User.objects.create_user(
            username="single@sc.ci", email="single@sc.ci", password=self.password,
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle_a, user=u, role="admin", permissions=["*"], active=True,
        )
        self.client.login(username="single@sc.ci", password=self.password)
        resp = self.client.get(reverse("mutuelles-list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(str(self.mutuelle_a.id), resp.url)

    def test_admin_navbar_shows_only_own_mutuelle(self):
        """La barre de navigation d'un admin mutuelle NE contient pas
        'Toutes les mutuelles' ni 'Plateforme'. Elle expose le nom de sa
        mutuelle + 'Membres'."""
        u = User.objects.create_user(
            username="nav@sc.ci", email="nav@sc.ci", password=self.password,
            first_name="Nav", last_name="ADMIN",
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle_a, user=u, role="admin", permissions=["*"], active=True,
        )
        u.default_mutuelle = self.mutuelle_a
        u.save(update_fields=["default_mutuelle"])
        self.client.login(username="nav@sc.ci", password=self.password)
        resp = self.client.get(reverse("dashboard-home"))
        self.assertEqual(resp.status_code, 200)
        # Contient le nom de sa mutuelle dans la nav
        self.assertContains(resp, "Mut A")
        # NE contient PAS "Toutes les mutuelles" (menu superadmin)
        self.assertNotContains(resp, "Toutes les mutuelles")
        # NE contient PAS le lien "Plateforme"
        self.assertNotContains(resp, "Plateforme")
        # NE voit PAS "Mut B" (isolation tenant respectée)
        self.assertNotContains(resp, "Mut B")

    def test_superadmin_navbar_shows_platform_and_all_mutuelles(self):
        root = User.objects.create_superuser(
            username="root@nav.ci", email="root@nav.ci", password=self.password,
        )
        self.client.login(username="root@nav.ci", password=self.password)
        resp = self.client.get(reverse("platform-center"))
        self.assertEqual(resp.status_code, 200)
        # Voit "Plateforme" dans la nav
        self.assertContains(resp, "Plateforme")
        # Menu "Toutes les mutuelles" visible
        self.assertContains(resp, "Toutes les mutuelles")

    def test_invite_landing_shows_pending_invitations(self):
        User.objects.create_user(
            username="inv@sc.ci", email="inv@sc.ci", password=self.password,
        )
        MemberInvitation.all_objects.create(
            mutuelle=self.mutuelle_a, email="inv@sc.ci",
            message="On vous attend !",
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.client.login(username="inv@sc.ci", password=self.password)
        resp = self.client.get(reverse("invite-landing"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mut A")
        self.assertContains(resp, "invitation")
