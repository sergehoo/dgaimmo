from io import StringIO

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_engine.models import AIAnalysis
from accounts.models import LoginEvent, OTPChallenge, UserDevice
from accounts.services import create_otp_challenge
from claims.models import AssistanceClaim
from governance.models import GeneralAssembly, Resolution
from memberships.models import Member
from mutuelles.models import Mutuelle
from contributions.models import Contribution, ContributionPlan
from notifications.models import Notification
from payments.models import Payment
from real_estate.models import PropertyDocument, RealEstateOpportunity, QuotiteCessibleSimulation
from real_estate.models import PropertyLot, PropertyReservation
from real_estate.models import RealEstateProgram
from real_estate.models import FinancingScenario, MortgageApplication


class DemoSeedAndDashboardTests(TestCase):
    def test_console_renders_without_active_mutuelle(self):
        User = get_user_model()
        User.objects.create_user(
            username="empty-admin@example.test",
            email="empty-admin@example.test",
            password="StrongPass123",
            role=User.Role.MUTUELLE_ADMIN,
        )
        self.assertTrue(self.client.login(username="empty-admin@example.test", password="StrongPass123"))

        response = self.client.get("/console/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tableau de bord")
        self.assertContains(response, "DGA-IMO360")

    def test_seed_demo_is_idempotent_and_dashboard_renders(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        call_command("seed_demo", stdout=output)

        self.assertEqual(Mutuelle.objects.filter(slug="dga-habitat").count(), 1)
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")
        self.assertEqual(Member.all_objects.filter(mutuelle=mutuelle).count(), 4)
        self.assertGreaterEqual(RealEstateOpportunity.all_objects.filter(mutuelle=mutuelle).count(), 1)
        self.assertGreaterEqual(QuotiteCessibleSimulation.all_objects.filter(mutuelle=mutuelle).count(), 4)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DGA-IMO360")
        self.assertContains(response, "Un réseau premium")

        protected_response = self.client.get("/console/")
        self.assertEqual(protected_response.status_code, 302)
        self.assertIn("/connexion/", protected_response["Location"])

        logged_in = self.client.login(username="admin@dga-habitat.test", password="StrongPass123")
        self.assertTrue(logged_in)

        console_response = self.client.get("/console/")
        self.assertEqual(console_response.status_code, 200)
        self.assertContains(console_response, "Tableau de bord")
        self.assertContains(console_response, "Quotité cessible par membre")
        self.assertContains(console_response, "Quotité cessible mensuelle")
        self.assertContains(console_response, "Amortissement")
        self.assertContains(console_response, "Vue opérationnelle")
        self.assertContains(console_response, "Funnel immobilier & financement")
        self.assertContains(console_response, "Dossiers immobiliers à suivre")
        self.assertContains(console_response, "Mutuelles récentes")

        list_response = self.client.get("/console/mutuelles/")
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Liste des mutuelles")
        self.assertContains(list_response, "DGA Habitat Mutuelle")

        detail_response = self.client.get(f"/console/mutuelles/{mutuelle.id}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Résumé financier")
        self.assertContains(detail_response, "Actions rapides")
        self.assertContains(detail_response, "Quotité cessible & solvabilité")
        self.assertContains(detail_response, "Période d'amortissement")
        self.assertContains(detail_response, "Programmes & opportunités")
        self.assertContains(detail_response, "Contrôle documentaire")
        self.assertContains(detail_response, "Cotisations & paiements")

        pages = {
            "/console/projets/": "Projets immobiliers",
            "/console/membres/": "Membres",
            "/console/simulations/": "Période d'amortissement",
            "/console/finances/": "Cotisations récentes",
            "/console/financements/": "Dossiers de financement",
            "/console/prestations/": "Demandes récentes",
            "/console/documents/": "Centre documentaire",
            "/console/notifications/": "Flux opérationnel",
            "/console/terrain-offline/": "File de synchronisation",
            "/console/ia/": "Historique intelligent",
            "/console/gouvernance/": "Résolutions & votes",
            "/console/branding/": "Identités configurées",
            "/console/securite/": "Journal de connexion",
            "/console/profil/": "Mon profil",
            "/console/rapports/": "Rapports par mutuelle",
        }
        for path, marker in pages.items():
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, marker)

        admin_response = self.client.get("/admin/")
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "Pilotage mutualiste")
        self.assertNotContains(admin_response, "admin-mutuellex.css")

    def test_console_forms_create_core_workflow_objects(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")

        mutuelle_response = self.client.post(
            "/console/mutuelles/nouvelle/",
            {
                "name": "Premium Network Habitat",
                "legal_name": "Premium Network Habitat SARL",
                "country": "CI",
                "currency": "XOF",
                "primary_color": "#003b98",
                "accent_color": "#0bbf63",
            },
        )
        self.assertEqual(mutuelle_response.status_code, 302)
        self.assertTrue(Mutuelle.objects.filter(slug="premium-network-habitat").exists())

        member_response = self.client.post(
            "/console/membres/nouveau/",
            {
                "mutuelle": mutuelle.id,
                "member_code": "DGA-999",
                "first_name": "Nadia",
                "last_name": "Yao",
                "phone": "+2250700099999",
                "email": "nadia@example.test",
                "status": "active",
                "kyc_validated": "on",
            },
        )
        self.assertEqual(member_response.status_code, 302)
        member = Member.all_objects.get(mutuelle=mutuelle, member_code="DGA-999")

        generated_member_response = self.client.post(
            "/console/membres/nouveau/",
            {
                "mutuelle": mutuelle.id,
                "member_code": "",
                "first_name": "Mariam",
                "last_name": "Bamba",
                "phone": "+2250700011111",
                "email": "mariam@example.test",
                "status": "active",
            },
        )
        self.assertEqual(generated_member_response.status_code, 302)
        generated_member = Member.all_objects.get(mutuelle=mutuelle, phone="+2250700011111")
        self.assertTrue(generated_member.member_code.startswith("DGAH-"))
        self.assertTrue(generated_member.qr_token.startswith(f"qr-{generated_member.member_code.lower()}-"))

        profile_response = self.client.post(
            "/console/profils-financiers/nouveau/",
            {
                "member": member.id,
                "net_monthly_salary": "800000",
                "complementary_income": "100000",
                "fixed_charges": "150000",
                "pensions": "0",
                "mutual_contributions": "25000",
                "dependents_count": "2",
                "professional_seniority_months": "48",
                "contract_type": "CDI",
                "employment_type": "private",
                "risk_level": "low",
            },
        )
        self.assertEqual(profile_response.status_code, 302)

        simulation_response = self.client.post(
            "/console/simulations/nouvelle/",
            {
                "member": member.id,
                "requested_amount": "18000000",
                "requested_duration_months": "120",
                "annual_interest_rate": "7",
                "max_debt_ratio": "33",
            },
        )
        self.assertEqual(simulation_response.status_code, 302)
        self.assertTrue(QuotiteCessibleSimulation.all_objects.filter(member=member).exists())

        project_response = self.client.post(
            "/console/projets/nouveau/",
            {
                "mutuelle": mutuelle.id,
                "program_name": "Cocody Signature",
                "city": "Abidjan",
                "total_lots": "8",
                "opportunity_title": "Appartement T4 Premium",
                "property_type": "apartment",
                "amount": "32000000",
                "initial_deposit": "6000000",
                "financing_months": "144",
                "lots_to_create": "2",
            },
        )
        self.assertEqual(project_response.status_code, 302)
        opportunity = RealEstateOpportunity.all_objects.get(title="Appartement T4 Premium")
        lot = PropertyLot.all_objects.filter(opportunity=opportunity).first()

        reservation_response = self.client.post(
            "/console/reservations/nouvelle/",
            {"lot": lot.id, "member": member.id, "deposit_paid": "500000", "decision_notes": "Réservation comité"},
        )
        self.assertEqual(reservation_response.status_code, 302)
        self.assertTrue(PropertyReservation.all_objects.filter(member=member, lot=lot).exists())

    def test_financing_center_creates_scenario_and_application(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")
        member = Member.all_objects.filter(mutuelle=mutuelle).first()
        opportunity = RealEstateOpportunity.all_objects.filter(mutuelle=mutuelle).first()

        response = self.client.get("/console/financements/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financements immobiliers")
        self.assertContains(response, "Dossiers de financement")

        scenario_response = self.client.post(
            "/console/financements/scenarios/nouveau/",
            {
                "member": member.id,
                "opportunity": opportunity.id,
                "mode": "mixed",
                "personal_deposit": "4000000",
                "duration_months": "144",
                "annual_interest_rate": "7",
            },
        )
        self.assertEqual(scenario_response.status_code, 302)
        scenario = FinancingScenario.all_objects.filter(member=member, opportunity=opportunity, mode="mixed").latest("created_at")

        application_response = self.client.post(
            "/console/financements/dossiers/nouveau/",
            {
                "scenario": scenario.id,
                "status": "draft",
                "committee_notes": "Dossier prêt pour comité.",
                "bank_reference": "BANK-TEST-001",
                "disbursed_amount": "0",
            },
        )
        self.assertEqual(application_response.status_code, 302)
        application = MortgageApplication.all_objects.get(scenario=scenario, bank_reference="BANK-TEST-001")
        self.assertEqual(application.member, member)

        advance_response = self.client.post(f"/console/financements/dossiers/{application.id}/avancer/")
        self.assertEqual(advance_response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, MortgageApplication.Status.COMMITTEE)

    def test_claims_center_creates_and_advances_assistance_claim(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")
        member = Member.all_objects.filter(mutuelle=mutuelle).first()

        response = self.client.get("/console/prestations/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prestations & assistance")
        self.assertContains(response, "Demandes récentes")

        create_response = self.client.post(
            "/console/prestations/nouvelle/",
            {
                "member": member.id,
                "claim_type": "accident",
                "beneficiary_name": f"{member.first_name} {member.last_name}",
                "incident_date": "2026-05-20",
                "amount": "150000",
                "currency": "XOF",
                "description": "Assistance accident avec justificatifs médicaux.",
                "status": "submitted",
                "approved_amount": "0",
                "decision_notes": "",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        claim = AssistanceClaim.all_objects.get(member=member, claim_type="accident")
        self.assertEqual(claim.mutuelle, mutuelle)

        advance_response = self.client.post(f"/console/prestations/{claim.id}/avancer/")
        self.assertEqual(advance_response.status_code, 302)
        claim.refresh_from_db()
        self.assertEqual(claim.status, AssistanceClaim.Status.REVIEW)

    def test_finance_forms_create_plan_contribution_and_payment(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")
        member = Member.all_objects.filter(mutuelle=mutuelle).first()

        plan_response = self.client.post(
            "/console/finances/plans/nouveau/",
            {
                "mutuelle": mutuelle.id,
                "name": "Cotisation premium",
                "frequency": "monthly",
                "amount": "35000",
                "penalty_rate": "2",
                "active": "on",
            },
        )
        self.assertEqual(plan_response.status_code, 302)
        plan = ContributionPlan.all_objects.get(mutuelle=mutuelle, name="Cotisation premium")

        contribution_response = self.client.post(
            "/console/finances/cotisations/nouvelle/",
            {
                "member": member.id,
                "plan": plan.id,
                "amount": "35000",
                "currency": "XOF",
                "due_date": "2026-06-01",
                "status": "paid",
                "penalty_amount": "0",
            },
        )
        self.assertEqual(contribution_response.status_code, 302)
        self.assertTrue(Contribution.all_objects.filter(member=member, plan=plan, status="paid").exists())

        payment_response = self.client.post(
            "/console/finances/paiements/nouveau/",
            {
                "member": member.id,
                "provider": "wave",
                "amount": "35000",
                "currency": "XOF",
                "phone": member.phone,
                "purpose": "contribution",
            },
        )
        self.assertEqual(payment_response.status_code, 302)
        self.assertTrue(Payment.all_objects.filter(member=member, provider="wave", status="pending").exists())
        payment = Payment.all_objects.get(member=member, provider="wave", status="pending")
        self.assertTrue(payment.external_reference.startswith("MM-WAV-"))

        simulate_response = self.client.post(f"/console/finances/paiements/{payment.id}/simuler-succes/")
        self.assertEqual(simulate_response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

        contribution = Contribution.all_objects.get(member=member, plan=plan, status="paid")
        receipt_response = self.client.get(f"/console/cotisations/{contribution.id}/recu.pdf")
        self.assertEqual(receipt_response.status_code, 200)
        self.assertEqual(receipt_response["Content-Type"], "application/pdf")
        self.assertTrue(receipt_response.content.startswith(b"%PDF"))

        export_response = self.client.get("/console/finances/export.csv")
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response["Content-Type"], "text/csv")
        self.assertContains(export_response, "Mutuelle,Membre,Plan,Montant")

    def test_document_upload_and_mutuelle_report_render(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")
        program = RealEstateProgram.all_objects.filter(mutuelle=mutuelle).first()

        upload_form = self.client.get("/console/documents/importer/")
        self.assertEqual(upload_form.status_code, 200)
        self.assertContains(upload_form, "Importer un document")

        uploaded_file = SimpleUploadedFile("titre-foncier.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        upload_response = self.client.post(
            "/console/documents/importer/",
            {
                "program": program.id,
                "document_type": "Titre foncier",
                "file": uploaded_file,
                "verified": "",
            },
        )
        self.assertEqual(upload_response.status_code, 302)
        document = PropertyDocument.all_objects.filter(program=program, document_type="Titre foncier").order_by("-created_at").first()
        self.assertEqual(document.mutuelle, mutuelle)
        self.assertEqual(document.ocr_payload["status"], "queued")

        ocr_response = self.client.post(f"/console/documents/{document.id}/ocr/")
        self.assertEqual(ocr_response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.ocr_payload["status"], "processed")
        self.assertEqual(document.ocr_payload["decision"], "verified")
        self.assertGreaterEqual(document.ocr_payload["confidence"], 80)
        self.assertTrue(document.verified)

        report_response = self.client.get(f"/console/mutuelles/{mutuelle.id}/rapport/")
        self.assertEqual(report_response.status_code, 200)
        self.assertContains(report_response, "Rapport de santé financière")
        self.assertContains(report_response, "DGA Habitat Mutuelle")
        self.assertContains(report_response, "Titre foncier")

        report_pdf = self.client.get(f"/console/mutuelles/{mutuelle.id}/rapport.pdf")
        self.assertEqual(report_pdf.status_code, 200)
        self.assertEqual(report_pdf["Content-Type"], "application/pdf")
        self.assertTrue(report_pdf.content.startswith(b"%PDF"))

    def test_notifications_center_and_create_form(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")
        member = Member.all_objects.filter(mutuelle=mutuelle).first()

        response = self.client.get("/console/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alertes & notifications")
        self.assertContains(response, "Rappel cotisation habitat")

        create_response = self.client.post(
            "/console/notifications/nouvelle/",
            {
                "mutuelle": mutuelle.id,
                "member": member.id,
                "channel": "sms",
                "title": "Alerte comité",
                "body": "Votre dossier passe en revue comité immobilier.",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        notification = Notification.all_objects.get(mutuelle=mutuelle, title="Alerte comité")
        self.assertEqual(notification.member, member)
        self.assertEqual(notification.status, Notification.Status.QUEUED)

    def test_ai_copilot_generates_decision_note(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")

        response = self.client.get("/console/ia/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Copilote IA immobilier")
        self.assertContains(response, "Historique intelligent")

        create_response = self.client.post(
            "/console/ia/note-decision/",
            {
                "mutuelle": mutuelle.id,
                "provider": "ollama",
                "prompt": "Préparer une note de décision banque et comité.",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        analysis = AIAnalysis.all_objects.filter(mutuelle=mutuelle, prompt="Préparer une note de décision banque et comité.").latest("created_at")
        self.assertEqual(analysis.analysis_type, "mutuelle_decision_note")
        self.assertIn(analysis.result["decision"], ["favorable", "favorable_sous_reserve", "defavorable"])
        self.assertIn("risks", analysis.result)

    def test_governance_center_and_forms(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")

        response = self.client.get("/console/gouvernance/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gouvernance")
        self.assertContains(response, "AG Programme Bingerville Habitat")

        assembly_response = self.client.post(
            "/console/gouvernance/assemblees/nouvelle/",
            {
                "mutuelle": mutuelle.id,
                "title": "AG Extraordinaire Riviera",
                "scheduled_at": "2026-07-01T10:00",
                "location": "Abidjan Riviera",
                "online_url": "",
                "status": "scheduled",
                "quorum_required": "55",
            },
        )
        self.assertEqual(assembly_response.status_code, 302)
        assembly = GeneralAssembly.all_objects.get(mutuelle=mutuelle, title="AG Extraordinaire Riviera")

        resolution_response = self.client.post(
            "/console/gouvernance/resolutions/nouvelle/",
            {
                "assembly": assembly.id,
                "title": "Autorisation négociation banque",
                "description": "Autoriser le bureau à négocier une garantie bancaire collective.",
                "status": "open",
                "approval_threshold": "60",
                "closes_at": "2026-07-10T18:00",
            },
        )
        self.assertEqual(resolution_response.status_code, 302)
        self.assertTrue(Resolution.all_objects.filter(mutuelle=mutuelle, assembly=assembly, title="Autorisation négociation banque").exists())

    def test_branding_center_updates_mutuelle_identity(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")

        response = self.client.get("/console/branding/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Branding mutuelle")
        self.assertContains(response, "DGA Habitat Mutuelle")

        update_response = self.client.post(
            f"/console/mutuelles/{mutuelle.id}/branding/",
            {
                "name": "DGA Habitat Signature",
                "legal_name": "DGA Habitat Mutuelle CI",
                "primary_color": "#003b98",
                "accent_color": "#12b76a",
            },
        )
        self.assertEqual(update_response.status_code, 302)
        mutuelle.refresh_from_db()
        self.assertEqual(mutuelle.name, "DGA Habitat Signature")
        self.assertEqual(mutuelle.accent_color, "#12b76a")

    def test_security_center_logs_devices_and_mfa(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        logged_in = self.client.login(username="admin@dga-habitat.test", password="StrongPass123")
        self.assertTrue(logged_in)
        mutuelle = Mutuelle.objects.get(slug="dga-habitat")
        user = mutuelle.default_users.get(email="admin@dga-habitat.test")

        response = self.client.get("/console/securite/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sécurité")
        self.assertContains(response, "Journal de connexion")

        challenge, code = create_otp_challenge(user)
        verify_response = self.client.post(
            "/console/securite/otp/verifier/",
            {"challenge": challenge.id, "code": code},
        )
        self.assertEqual(verify_response.status_code, 302)
        user.refresh_from_db()
        challenge.refresh_from_db()
        self.assertTrue(user.mfa_enabled)
        self.assertEqual(challenge.status, OTPChallenge.Status.VERIFIED)

        login_response = self.client.post(
            "/connexion/",
            {"username": "admin@dga-habitat.test", "password": "StrongPass123"},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(LoginEvent.objects.filter(email="admin@dga-habitat.test", status=LoginEvent.Status.SUCCESS).exists())
        self.assertTrue(UserDevice.objects.filter(user=user).exists())

    def test_connected_user_can_update_profile_and_password(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        self.assertTrue(self.client.login(username="admin@dga-habitat.test", password="StrongPass123"))

        response = self.client.get("/console/profil/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informations personnelles")
        self.assertContains(response, "Mot de passe")

        profile_response = self.client.post(
            "/console/profil/",
            {
                "form_kind": "profile",
                "first_name": "Serge",
                "last_name": "Ogah",
                "email": "serge.ogah@example.test",
                "phone": "+2250700000001",
            },
        )
        self.assertEqual(profile_response.status_code, 200)
        user = get_user_model().objects.get(email="serge.ogah@example.test")
        self.assertEqual(user.username, "serge.ogah@example.test")
        self.assertEqual(user.phone, "+2250700000001")

        password_response = self.client.post(
            "/console/profil/",
            {
                "form_kind": "password",
                "old_password": "StrongPass123",
                "new_password1": "StrongPass456",
                "new_password2": "StrongPass456",
            },
        )
        self.assertEqual(password_response.status_code, 200)
        self.assertContains(password_response, "Mot de passe mis à jour")

        self.client.logout()
        self.assertFalse(self.client.login(username="serge.ogah@example.test", password="StrongPass123"))
        self.assertTrue(self.client.login(username="serge.ogah@example.test", password="StrongPass456"))
