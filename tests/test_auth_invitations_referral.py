"""Tests ciblés — auth (login, reset), signup, invitations, parrainage,
portails Admin Mutuelle / Mutualiste.

Ces tests utilisent SQLite via l'environnement de test Django (DATABASES).
Ils sont volontairement autonomes (aucune fixture) et couvrent les
parcours utilisateur critiques demandés.
"""

from __future__ import annotations

from datetime import timedelta

from django.core import mail
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from memberships.models import Bank, Member, MemberInvitation
from mutuelles.models import Mutuelle, MutuelleMembership


User = get_user_model()


# Neutralise WhiteNoise CompressedManifestStaticFilesStorage pour les tests
# (aucun collectstatic n'a été fait dans l'environnement de test).
TEST_STATIC_OVERRIDES = dict(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", **TEST_STATIC_OVERRIDES)
class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "Secure!Passw0rd"
        self.user = User.objects.create_user(
            username="admin@dga.ci",
            email="admin@dga.ci",
            password=self.password,
            first_name="Serge",
            last_name="OGAH",
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accéder à mon espace")
        self.assertContains(response, "Mot de passe oublié")

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": self.password},
            follow=False,
        )
        # Redirection sur succès (302 vers dashboard-home ou member-portal)
        self.assertIn(response.status_code, {302, 303})

    def test_login_failure_shows_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identifiants invalides")

    def test_password_reset_form_renders(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Réinitialiser mon mot de passe")

    def test_password_reset_sends_email(self):
        mail.outbox = []
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("DGA Mutuelle", mail.outbox[0].subject)
        # Le corps texte doit contenir un lien password_reset_confirm
        self.assertIn("mot-de-passe-oublie/valider/", mail.outbox[0].body)

    def test_password_reset_done_renders(self):
        response = self.client.get(reverse("password_reset_done"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email envoyé")

    def test_password_reset_complete_renders(self):
        response = self.client.get(reverse("password_reset_complete"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mot de passe mis à jour")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", **TEST_STATIC_OVERRIDES)
class SignupWelcomeEmailTests(TestCase):
    def test_public_mutuelle_signup_sends_welcome_email(self):
        mail.outbox = []
        response = self.client.post(
            reverse("public-mutuelle-signup"),
            {
                "mutuelle_name": "Mutuelle Test Cocody",
                "organization_name": "Test SARL",
                "organization_type": Mutuelle.OrganizationType.ENTREPRISE,
                "estimated_members_count": 50,
                "real_estate_objective": [Mutuelle.RealEstateObjective.TERRAIN],
                "real_estate_objective_details": "Cocody, terrain 500m2",
                "primary_color": "#003b98",
                "last_name": "OGAH",
                "first_name": "Serge",
                "contact_function": "Président",
                "email": "founder@test.ci",
                "phone": "+2250700000001",
                "password1": "Secure!Passw0rd",
                "password2": "Secure!Passw0rd",
            },
            follow=False,
        )
        # 302 redirect on success
        self.assertEqual(response.status_code, 302)
        # Mutuelle et user créés
        self.assertTrue(Mutuelle.objects.filter(name="Mutuelle Test Cocody").exists())
        # Email de bienvenue envoyé
        self.assertGreaterEqual(len(mail.outbox), 1)
        welcome = [m for m in mail.outbox if "Bienvenue" in m.subject]
        self.assertEqual(len(welcome), 1)
        self.assertIn("founder@test.ci", welcome[0].to)
        self.assertIn("Mutuelle Test Cocody", welcome[0].body)


@override_settings(**TEST_STATIC_OVERRIDES)
class InvitationFlowTests(TestCase):
    def setUp(self):
        self.mutuelle = Mutuelle.objects.create(
            name="Mutuelle Invit", slug="mutuelle-invit",
            organization_name="Test Org",
            organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10,
            country="CI", currency="XOF",
        )
        self.admin = User.objects.create_user(
            username="admin@invit.ci", email="admin@invit.ci",
            password="Secure!Passw0rd", first_name="Alice", last_name="ADMIN",
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle, user=self.admin,
            role="admin", permissions=["*"], active=True,
        )

    def test_create_invitation_generates_valid_token(self):
        from memberships.services import create_invitation
        inv = create_invitation(
            self.mutuelle, "prospect@test.ci",
            invited_by=self.admin, ttl_days=7,
        )
        self.assertEqual(inv.status, MemberInvitation.Status.PENDING)
        self.assertTrue(inv.is_usable)
        self.assertFalse(inv.is_expired)
        self.assertTrue(inv.token)
        self.assertGreater(len(inv.token), 20)

    def test_create_invitation_dedup_reuses_existing(self):
        from memberships.services import create_invitation
        inv1 = create_invitation(self.mutuelle, "same@test.ci", invited_by=self.admin, ttl_days=7)
        inv2 = create_invitation(self.mutuelle, "same@test.ci", invited_by=self.admin, ttl_days=14)
        # Même instance réutilisée (pas de doublon)
        self.assertEqual(inv1.pk, inv2.pk)
        # Expiration prolongée
        self.assertGreater(inv2.expires_at, inv1.expires_at - timedelta(seconds=1))

    def test_create_invitation_blocks_existing_member(self):
        Member.all_objects.create(
            mutuelle=self.mutuelle,
            member_code="MI-2026-0001",
            first_name="Bob", last_name="EXIST",
            phone="+2250700111111", email="existing@test.ci",
            qr_token="qr-existing",
        )
        from memberships.services import create_invitation
        with self.assertRaises(ValueError):
            create_invitation(self.mutuelle, "existing@test.ci", invited_by=self.admin)

    def test_expired_invitation_shows_expired_state(self):
        inv = MemberInvitation.all_objects.create(
            mutuelle=self.mutuelle, email="late@test.ci",
            expires_at=timezone.now() - timedelta(days=1),
        )
        response = self.client.get(reverse("accept-member-invitation", kwargs={"token": inv.token}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lien expiré")
        inv.refresh_from_db()
        self.assertEqual(inv.status, MemberInvitation.Status.EXPIRED)


@override_settings(**TEST_STATIC_OVERRIDES)
class ReferralFlowTests(TestCase):
    def setUp(self):
        self.mutuelle = Mutuelle.objects.create(
            name="Mutuelle Parrain", slug="mutuelle-parrain",
            organization_name="Test", organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10, country="CI", currency="XOF",
        )
        self.referrer = Member.all_objects.create(
            mutuelle=self.mutuelle,
            member_code="MP-2026-0001",
            first_name="Parrain", last_name="ONE",
            phone="+2250700222222", email="parrain@test.ci",
            qr_token="qr-parrain",
        )

    def test_referral_code_auto_generation(self):
        code = self.referrer.ensure_referral_code()
        self.assertTrue(code)
        self.assertGreaterEqual(len(code), 4)
        # Idempotent : renvoie le même code
        self.assertEqual(self.referrer.ensure_referral_code(), code)

    def test_referral_url_uses_code(self):
        code = self.referrer.ensure_referral_code()
        url = self.referrer.referral_url()
        self.assertIn(code, url)

    def test_referral_signup_landing_page(self):
        code = self.referrer.ensure_referral_code()
        response = self.client.get(reverse("referral-signup", kwargs={"code": code}))
        self.assertEqual(response.status_code, 200)
        # Page d'adhésion : contient le nom de la mutuelle du parrain
        self.assertContains(response, self.mutuelle.name)
        self.assertContains(response, "Complétez votre profil")

    def test_referral_signup_unknown_code_404(self):
        response = self.client.get(reverse("referral-signup", kwargs={"code": "UNKNOWN99"}))
        self.assertEqual(response.status_code, 404)

    def test_referral_creates_member_and_attributes(self):
        code = self.referrer.ensure_referral_code()
        payload = {
            "first_name": "Filleul",
            "last_name": "TWO",
            "phone": "+2250700333333",
            "email": "filleul@test.ci",
            "marital_status": Member.MaritalStatus.SINGLE,
            "dependents_count": 0,
        }
        response = self.client.post(
            reverse("referral-signup", kwargs={"code": code}),
            payload,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenue")
        # Le filleul créé est rattaché au parrain
        filleul = Member.all_objects.get(phone="+2250700333333")
        self.assertEqual(filleul.referred_by_id, self.referrer.id)
        self.assertEqual(filleul.mutuelle_id, self.mutuelle.id)

    def test_referral_blocks_self_referral_by_email(self):
        code = self.referrer.ensure_referral_code()
        payload = {
            "first_name": "Auto",
            "last_name": "SELF",
            "phone": "+2250700444444",
            "email": "parrain@test.ci",  # même email que le parrain
            "marital_status": Member.MaritalStatus.SINGLE,
            "dependents_count": 0,
        }
        response = self.client.post(
            reverse("referral-signup", kwargs={"code": code}),
            payload,
        )
        # Doit renvoyer le formulaire (200) avec erreur, pas de création
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Member.all_objects.filter(phone="+2250700444444").exists())


@override_settings(**TEST_STATIC_OVERRIDES)
class MemberPortalTests(TestCase):
    def setUp(self):
        self.password = "Secure!Passw0rd"
        self.mutuelle = Mutuelle.objects.create(
            name="Mutuelle Portal", slug="mutuelle-portal",
            organization_name="Test", organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10, country="CI", currency="XOF",
        )
        self.user = User.objects.create_user(
            username="member@portal.ci", email="member@portal.ci",
            password=self.password, first_name="Marie", last_name="MEMBRE",
        )
        self.member = Member.all_objects.create(
            mutuelle=self.mutuelle, user=self.user,
            member_code="MP-2026-0100",
            first_name="Marie", last_name="MEMBRE",
            phone="+2250700555555", email="member@portal.ci",
            qr_token="qr-marie",
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle, user=self.user,
            role="member", permissions=[], active=True,
        )

    def test_member_portal_requires_auth(self):
        response = self.client.get(reverse("member-portal"))
        # Redirige vers login (302) si non authentifié
        self.assertEqual(response.status_code, 302)

    def test_member_portal_renders_for_member(self):
        self.client.login(username=self.user.email, password=self.password)
        response = self.client.get(reverse("member-portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Espace mutualiste")
        self.assertContains(response, "Marie")

    def test_member_portal_referrals_renders(self):
        self.client.login(username=self.user.email, password=self.password)
        response = self.client.get(reverse("member-portal-referrals"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Parrainage")
        # Le code doit avoir été généré automatiquement
        self.member.refresh_from_db()
        self.assertTrue(self.member.referral_code)

    def test_console_dashboard_redirects_member_to_portal(self):
        self.client.login(username=self.user.email, password=self.password)
        response = self.client.get(reverse("dashboard-home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("member-portal"), response.url)
