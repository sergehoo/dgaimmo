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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", **TEST_STATIC_OVERRIDES)
class InvitationEndToEndTests(TestCase):
    """Parcours complet : invitation depuis la liste des membres → email →
    acceptation par le prospect → membre actif + compte connecté."""

    def setUp(self):
        self.password = "Secure!Passw0rd"
        self.mutuelle = Mutuelle.objects.create(
            name="Mutuelle E2E", slug="mutuelle-e2e",
            organization_name="E2E Org",
            organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=10, country="CI", currency="XOF",
        )
        self.admin = User.objects.create_user(
            username="admin@e2e.ci", email="admin@e2e.ci",
            password=self.password, first_name="Awa", last_name="ADMIN",
            role=User.Role.MUTUELLE_ADMIN, default_mutuelle=self.mutuelle,
        )
        MutuelleMembership.objects.create(
            mutuelle=self.mutuelle, user=self.admin,
            role="admin", permissions=["*"], active=True,
        )
        self.admin_client = Client()
        self.admin_client.login(username=self.admin.email, password=self.password)
        mail.outbox = []

    # --- Liste des membres : formulaire d'invitation --------------------------
    def test_members_center_shows_invite_form(self):
        response = self.admin_client.get(reverse("members-center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inviter par email")
        self.assertContains(response, reverse("invite-member"))
        self.assertContains(response, "Invitations en attente")

    def test_quick_invite_requires_login(self):
        response = self.client.post(reverse("invite-member"), {"email": "x@e2e.ci"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_quick_invite_creates_invitation_and_sends_email(self):
        response = self.admin_client.post(
            reverse("invite-member"),
            {"email": "Prospect@E2E.ci", "full_name": "Koffi PROSPECT", "message": "Bienvenue !"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("members-center"))

        inv = MemberInvitation.all_objects.get(mutuelle=self.mutuelle, email="prospect@e2e.ci")
        self.assertEqual(inv.status, MemberInvitation.Status.SENT)
        self.assertEqual(inv.full_name, "Koffi PROSPECT")
        self.assertEqual(inv.invited_by_id, self.admin.id)
        self.assertIsNotNone(inv.sent_at)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["prospect@e2e.ci"])
        self.assertIn(self.mutuelle.name, email.subject)
        self.assertIn(reverse("accept-member-invitation", kwargs={"token": inv.token}), email.body)
        self.assertIn("Bienvenue !", email.body)

        # L'invitation apparaît ensuite dans la liste des membres
        listing = self.admin_client.get(reverse("members-center"))
        self.assertContains(listing, "prospect@e2e.ci")
        self.assertContains(listing, "Invitation envoyée à prospect@e2e.ci")

    def test_quick_invite_rejects_existing_member(self):
        Member.all_objects.create(
            mutuelle=self.mutuelle, member_code="E2E-0001",
            first_name="Deja", last_name="LA", phone="+2250700000009",
            email="deja@e2e.ci", qr_token="qr-deja",
        )
        response = self.admin_client.post(reverse("invite-member"), {"email": "deja@e2e.ci"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MemberInvitation.all_objects.filter(email="deja@e2e.ci").exists())
        self.assertContains(response, "déjà enregistré")
        self.assertEqual(len(mail.outbox), 0)

    def test_quick_invite_invalid_email(self):
        response = self.admin_client.post(reverse("invite-member"), {"email": "pas-un-email"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MemberInvitation.all_objects.exists())

    # --- Acceptation par le prospect ------------------------------------------
    def _invite(self, email="new@e2e.ci", **kwargs):
        from memberships.services import create_invitation
        return create_invitation(self.mutuelle, email, invited_by=self.admin, **kwargs)

    def _accept_payload(self, **overrides):
        payload = {
            "first_name": "Nouveau",
            "last_name": "MEMBRE",
            "phone": "+2250700777777",
            "marital_status": Member.MaritalStatus.SINGLE,
            "dependents_count": 0,
            "password1": "MonSuperMdp!2026",
            "password2": "MonSuperMdp!2026",
        }
        payload.update(overrides)
        return payload

    def test_accept_page_locks_email_and_asks_password(self):
        inv = self._invite(full_name="Nouveau MEMBRE")
        response = self.client.get(reverse("accept-member-invitation", kwargs={"token": inv.token}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complétez votre profil")
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertContains(response, 'value="new@e2e.ci"')
        self.assertContains(response, "disabled")
        # Pré-remplissage depuis le nom saisi par l'admin
        self.assertContains(response, 'value="Nouveau"')

    def test_accept_creates_active_member_user_and_logs_in(self):
        inv = self._invite()
        url = reverse("accept-member-invitation", kwargs={"token": inv.token})
        # Tentative de changer l'email : ignorée, l'email reste celui de l'invitation
        response = self.client.post(url, self._accept_payload(email="autre@evil.ci"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenue")
        self.assertContains(response, reverse("member-portal"))

        member = Member.all_objects.get(mutuelle=self.mutuelle, phone="+2250700777777")
        self.assertEqual(member.email, "new@e2e.ci")
        self.assertEqual(member.status, Member.Status.ACTIVE)
        self.assertIsNotNone(member.joined_at)
        self.assertTrue(member.member_code)
        self.assertTrue(member.referral_code)
        self.assertEqual(member.metadata.get("onboarding"), "invitation")

        user = User.objects.get(email="new@e2e.ci")
        self.assertTrue(user.check_password("MonSuperMdp!2026"))
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertEqual(user.default_mutuelle_id, self.mutuelle.id)
        self.assertEqual(member.user_id, user.id)
        self.assertTrue(
            MutuelleMembership.objects.filter(mutuelle=self.mutuelle, user=user, role="member", active=True).exists()
        )

        inv.refresh_from_db()
        self.assertEqual(inv.status, MemberInvitation.Status.ACCEPTED)
        self.assertEqual(inv.member_id, member.id)
        self.assertIsNotNone(inv.used_at)

        # Connecté automatiquement : l'espace mutualiste est accessible
        portal = self.client.get(reverse("member-portal"))
        self.assertEqual(portal.status_code, 200)
        self.assertContains(portal, "Nouveau")

        # Email de bienvenue envoyé au nouveau membre
        welcome = [m for m in mail.outbox if "Bienvenue" in m.subject]
        self.assertEqual(len(welcome), 1)
        self.assertEqual(welcome[0].to, ["new@e2e.ci"])

        # Le lien ne peut plus être réutilisé
        again = self.client.get(url)
        self.assertContains(again, "Invitation déjà acceptée")

    def test_accept_password_mismatch_blocks_creation(self):
        inv = self._invite()
        response = self.client.post(
            reverse("accept-member-invitation", kwargs={"token": inv.token}),
            self._accept_payload(password2="Different!2026"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ne correspondent pas")
        self.assertFalse(Member.all_objects.filter(phone="+2250700777777").exists())
        self.assertFalse(User.objects.filter(email="new@e2e.ci").exists())
        inv.refresh_from_db()
        self.assertEqual(inv.status, MemberInvitation.Status.PENDING)

    def test_accept_missing_password_blocks_creation(self):
        inv = self._invite()
        payload = self._accept_payload()
        payload.pop("password1")
        payload.pop("password2")
        response = self.client.post(reverse("accept-member-invitation", kwargs={"token": inv.token}), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Member.all_objects.filter(phone="+2250700777777").exists())

    def test_accept_duplicate_phone_blocked(self):
        Member.all_objects.create(
            mutuelle=self.mutuelle, member_code="E2E-0002",
            first_name="Tel", last_name="PRIS", phone="+2250700777777",
            email="tel@e2e.ci", qr_token="qr-tel",
        )
        inv = self._invite()
        response = self.client.post(
            reverse("accept-member-invitation", kwargs={"token": inv.token}), self._accept_payload()
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "déjà enregistré")
        self.assertFalse(Member.all_objects.filter(email="new@e2e.ci").exists())

    def test_accept_with_existing_user_links_account_without_password(self):
        existing = User.objects.create_user(
            username="exist@e2e.ci", email="exist@e2e.ci", password="OldPassw0rd!",
        )
        inv = self._invite(email="exist@e2e.ci")
        url = reverse("accept-member-invitation", kwargs={"token": inv.token})

        page = self.client.get(url)
        self.assertNotContains(page, 'name="password1"')
        self.assertContains(page, "Un compte existe déjà")

        payload = self._accept_payload()
        payload.pop("password1")
        payload.pop("password2")
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenue")
        # Pas de connexion automatique : bouton "Se connecter"
        self.assertContains(response, reverse("login"))

        member = Member.all_objects.get(email="exist@e2e.ci")
        self.assertEqual(member.user_id, existing.id)
        self.assertEqual(member.status, Member.Status.ACTIVE)
        existing.refresh_from_db()
        self.assertTrue(existing.check_password("OldPassw0rd!"))
        self.assertEqual(existing.default_mutuelle_id, self.mutuelle.id)
        self.assertTrue(MutuelleMembership.objects.filter(mutuelle=self.mutuelle, user=existing).exists())

    # --- Gestion des invitations en attente ----------------------------------
    def test_cancel_invitation_makes_link_unusable(self):
        inv = self._invite()
        response = self.admin_client.post(reverse("cancel-member-invitation", kwargs={"invitation_id": inv.id}))
        self.assertEqual(response.status_code, 302)
        inv.refresh_from_db()
        self.assertEqual(inv.status, MemberInvitation.Status.CANCELLED)
        page = self.client.get(reverse("accept-member-invitation", kwargs={"token": inv.token}))
        self.assertContains(page, "Lien expiré")
        # Une nouvelle invitation peut être générée pour le même email
        new_inv = self._invite()
        self.assertNotEqual(new_inv.pk, inv.pk)

    def test_resend_invitation_sends_mail_and_extends_expiry(self):
        inv = self._invite(ttl_days=1)
        response = self.admin_client.post(reverse("resend-member-invitation", kwargs={"invitation_id": inv.id}))
        self.assertEqual(response.status_code, 302)
        inv.refresh_from_db()
        self.assertEqual(inv.status, MemberInvitation.Status.SENT)
        self.assertGreater(inv.expires_at, timezone.now() + timedelta(days=13))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@e2e.ci"])

    def test_admin_cannot_manage_other_mutuelle_invitation(self):
        other = Mutuelle.objects.create(
            name="Autre Mutuelle", slug="autre-mutuelle",
            organization_name="Autre", organization_type=Mutuelle.OrganizationType.ENTREPRISE,
            estimated_members_count=5, country="CI", currency="XOF",
        )
        inv = MemberInvitation.all_objects.create(
            mutuelle=other, email="autre@e2e.ci", expires_at=timezone.now() + timedelta(days=7),
        )
        response = self.admin_client.post(reverse("cancel-member-invitation", kwargs={"invitation_id": inv.id}))
        self.assertEqual(response.status_code, 404)
        inv.refresh_from_db()
        self.assertEqual(inv.status, MemberInvitation.Status.PENDING)
        # Et elle n'apparaît pas dans sa liste des membres
        listing = self.admin_client.get(reverse("members-center"))
        self.assertNotContains(listing, "autre@e2e.ci")
