from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ai_engine.models import AIAnalysis
from ai_engine.services import generate_mutuelle_decision_note
from claims.models import AssistanceClaim
from contributions.models import Contribution, ContributionPlan
from core.models import TenantQuota
from governance.models import GeneralAssembly, Resolution, ResolutionVote
from memberships.models import Member
from mutuelles.models import Mutuelle, MutuelleMembership
from notifications.models import Notification
from notifications.services import queue_notification
from real_estate.models import (
    FinancingScenario,
    MemberFinancialProfile,
    MortgageApplication,
    PropertyLot,
    PropertyDocument,
    PropertyReservation,
    RealEstateOpportunity,
    RealEstateProgram,
)
from real_estate.services import compute_member_score, compute_mutuelle_score, compute_program_score, create_financing_scenario, simulate_quotite
from treasury.models import CashAccount, LedgerEntry


class Command(BaseCommand):
    help = "Seed a complete MutuelleX MVP demo tenant."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        mutuelle, _ = Mutuelle.objects.update_or_create(
            slug="dga-habitat",
            defaults={
                "name": "DGA Habitat Mutuelle",
                "legal_name": "DGA Habitat Mutuelle CI",
                "country": "CI",
                "currency": "XOF",
                "status": Mutuelle.Status.ACTIVE,
                "subscription_plan": "enterprise-demo",
            },
        )
        admin, created = User.objects.get_or_create(
            email="admin@dga-habitat.test",
            defaults={
                "username": "admin@dga-habitat.test",
                "first_name": "Serge",
                "last_name": "Admin",
                "phone": "+2250700000100",
                "role": User.Role.MUTUELLE_ADMIN,
                "default_mutuelle": mutuelle,
                "is_staff": True,
            },
        )
        if created:
            admin.set_password("StrongPass123")
            admin.save(update_fields=["password"])
        else:
            admin.default_mutuelle = mutuelle
            admin.role = User.Role.MUTUELLE_ADMIN
            admin.is_staff = True
            admin.save(update_fields=["default_mutuelle", "role", "is_staff"])

        MutuelleMembership.objects.update_or_create(
            mutuelle=mutuelle, user=admin, defaults={"role": User.Role.MUTUELLE_ADMIN, "permissions": ["*"], "active": True}
        )
        TenantQuota.objects.update_or_create(mutuelle=mutuelle, defaults={"max_members": 5000, "max_monthly_ai_calls": 10000})

        cash, _ = CashAccount.all_objects.update_or_create(
            mutuelle=mutuelle,
            name="Caisse principale",
            defaults={"account_type": CashAccount.AccountType.MAIN, "balance": Decimal("184000000"), "currency": "XOF", "active": True},
        )
        LedgerEntry.all_objects.get_or_create(
            mutuelle=mutuelle,
            cash_account=cash,
            reference="OPENING-2026",
            defaults={
                "direction": LedgerEntry.Direction.CREDIT,
                "category": "opening_balance",
                "amount": Decimal("184000000"),
                "currency": "XOF",
                "description": "Solde initial de démonstration",
                "occurred_at": timezone.now(),
            },
        )

        plan, _ = ContributionPlan.all_objects.update_or_create(
            mutuelle=mutuelle,
            name="Cotisation mensuelle habitat",
            defaults={"frequency": ContributionPlan.Frequency.MONTHLY, "amount": Decimal("25000"), "active": True},
        )

        members_payload = [
            ("DGA-001", "Awa", "Kone", "+2250700000101", Decimal("650000"), "public"),
            ("DGA-002", "Mariam", "Traore", "+2250700000102", Decimal("480000"), "private"),
            ("DGA-003", "Jean", "Kouadio", "+2250700000103", Decimal("900000"), "private"),
            ("DGA-004", "Fatou", "Bamba", "+2250700000104", Decimal("350000"), "independent"),
        ]
        members = []
        for code, first_name, last_name, phone, salary, employment_type in members_payload:
            member, _ = Member.all_objects.update_or_create(
                mutuelle=mutuelle,
                member_code=code,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "qr_token": f"qr-{code.lower()}",
                    "status": Member.Status.ACTIVE,
                    "joined_at": timezone.now().date(),
                    "kyc_validated": True,
                },
            )
            MemberFinancialProfile.all_objects.update_or_create(
                mutuelle=mutuelle,
                member=member,
                defaults={
                    "net_monthly_salary": salary,
                    "complementary_income": Decimal("75000"),
                    "fixed_charges": Decimal("120000"),
                    "mutual_contributions": Decimal("25000"),
                    "dependents_count": 2,
                    "employment_type": employment_type,
                    "risk_level": "low" if salary >= Decimal("600000") else "medium",
                },
            )
            Contribution.all_objects.update_or_create(
                mutuelle=mutuelle,
                member=member,
                plan=plan,
                due_date=timezone.now().date(),
                defaults={"amount": plan.amount, "currency": "XOF", "status": Contribution.Status.PAID, "paid_at": timezone.now()},
            )
            simulate_quotite(mutuelle, member, Decimal("20000000"), 120, 7, 33)
            compute_member_score(mutuelle, member)
            members.append(member)

        program, _ = RealEstateProgram.all_objects.update_or_create(
            mutuelle=mutuelle,
            name="Bingerville Habitat Tranche 1",
            defaults={
                "city": "Bingerville",
                "country": "CI",
                "total_lots": 40,
                "status": RealEstateProgram.Status.ACTIVE,
                "legal_status": "ACD en vérification",
                "documents_checklist": {"titre_foncier": True, "permis_construire": True, "contrat_promoteur": False},
            },
        )
        opportunity, _ = RealEstateOpportunity.all_objects.update_or_create(
            mutuelle=mutuelle,
            program=program,
            title="Villa F4 évolutive",
            defaults={
                "property_type": RealEstateOpportunity.PropertyType.VILLA,
                "amount": Decimal("25000000"),
                "currency": "XOF",
                "initial_deposit": Decimal("5000000"),
                "financing_months": 120,
                "estimated_monthly_payment": Decimal("232000"),
                "available_lots": 12,
                "interested_members_count": len(members),
                "status": RealEstateOpportunity.Status.AVAILABLE,
                "score": Decimal("76.00"),
            },
        )
        lot, _ = PropertyLot.all_objects.update_or_create(
            mutuelle=mutuelle,
            opportunity=opportunity,
            lot_number="VILLA-A01",
            defaults={"surface_area": Decimal("120"), "amount": Decimal("25000000"), "currency": "XOF", "status": PropertyLot.Status.RESERVED},
        )
        scenario = create_financing_scenario(mutuelle, members[0], opportunity, FinancingScenario.Mode.MUTUELLE_LOAN, Decimal("5000000"), 120, 7)
        MortgageApplication.all_objects.update_or_create(
            mutuelle=mutuelle,
            member=members[0],
            scenario=scenario,
            defaults={
                "status": MortgageApplication.Status.COMMITTEE,
                "committee_notes": "Dossier prioritaire pour revue comité immobilier.",
                "bank_reference": "DGA-BANK-DEMO-001",
                "disbursed_amount": Decimal("0"),
            },
        )
        PropertyReservation.all_objects.update_or_create(
            mutuelle=mutuelle,
            lot=lot,
            member=members[0],
            defaults={"status": PropertyReservation.Status.PENDING, "deposit_paid": Decimal("500000")},
        )
        if not PropertyDocument.all_objects.filter(mutuelle=mutuelle, program=program, document_type="Titre foncier").exists():
            document = PropertyDocument.all_objects.create(
                mutuelle=mutuelle,
                program=program,
                document_type="Titre foncier",
                ocr_payload={"status": "queued", "engine": "hybrid_ocr", "message": "Document prêt pour OCR."},
            )
            document.file.save("titre-foncier-demo.pdf", ContentFile(b"%PDF-1.4 demo titre foncier"), save=True)
        compute_program_score(mutuelle, program)
        score = compute_mutuelle_score(mutuelle)

        notification_payloads = [
            (
                Notification.Channel.WHATSAPP,
                "Rappel cotisation habitat",
                "Votre cotisation mensuelle est disponible. Payez via Mobile Money pour conserver votre priorité programme.",
                members[1],
            ),
            (
                Notification.Channel.REALTIME,
                "Document promoteur à compléter",
                "Le contrat promoteur du programme Bingerville Habitat Tranche 1 doit être validé avant transmission banque.",
                None,
            ),
            (
                Notification.Channel.SMS,
                "Simulation favorable",
                "Votre quotité cessible permet une étude comité pour la Villa F4 évolutive.",
                members[0],
            ),
        ]
        for channel, title, body, member in notification_payloads:
            if not Notification.all_objects.filter(mutuelle=mutuelle, title=title).exists():
                queue_notification(
                    mutuelle=mutuelle,
                    title=title,
                    body=body,
                    channel=channel,
                    member=member,
                    metadata={"source": "seed_demo", "segment": "real_estate"},
                )

        if not AIAnalysis.all_objects.filter(mutuelle=mutuelle, analysis_type="mutuelle_decision_note").exists():
            AIAnalysis.all_objects.create(
                mutuelle=mutuelle,
                analysis_type="mutuelle_decision_note",
                provider=AIAnalysis.Provider.OLLAMA,
                prompt="Produire une note de décision comité pour programme immobilier mutualiste.",
                result=generate_mutuelle_decision_note(mutuelle),
                confidence=82,
                related_object_type="Mutuelle",
                related_object_id=str(mutuelle.id),
            )

        assembly, _ = GeneralAssembly.all_objects.update_or_create(
            mutuelle=mutuelle,
            title="AG Programme Bingerville Habitat",
            defaults={
                "scheduled_at": timezone.now() + timezone.timedelta(days=21),
                "location": "Abidjan Cocody",
                "online_url": "https://meet.dga-imo360.local/ag-bingerville",
                "status": GeneralAssembly.Status.SCHEDULED,
                "quorum_required": 60,
            },
        )
        resolution, _ = Resolution.all_objects.update_or_create(
            mutuelle=mutuelle,
            assembly=assembly,
            title="Validation du programme Bingerville Habitat Tranche 1",
            defaults={
                "description": "Autoriser la mutuelle à poursuivre la constitution des dossiers membres et la négociation bancaire.",
                "status": Resolution.Status.OPEN,
                "approval_threshold": 66,
                "closes_at": timezone.now() + timezone.timedelta(days=14),
            },
        )
        ResolutionVote.all_objects.update_or_create(
            mutuelle=mutuelle,
            resolution=resolution,
            member=members[0],
            defaults={"choice": ResolutionVote.Choice.YES, "signed_hash": "seeded-vote-hash"},
        )
        AssistanceClaim.all_objects.update_or_create(
            mutuelle=mutuelle,
            member=members[2],
            claim_type=AssistanceClaim.ClaimType.ILLNESS,
            defaults={
                "status": AssistanceClaim.Status.REVIEW,
                "beneficiary_name": "Jean Kouadio",
                "incident_date": timezone.now().date(),
                "amount": Decimal("250000"),
                "currency": "XOF",
                "approved_amount": Decimal("0"),
                "description": "Demande de prise en charge médicale pour soins spécialisés.",
                "decision_notes": "Documents médicaux en cours de revue.",
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo MutuelleX seeded."))
        self.stdout.write(f"Admin: admin@dga-habitat.test / StrongPass123")
        self.stdout.write(f"Mutuelle: {mutuelle.name} ({mutuelle.id})")
        self.stdout.write(f"Scenario: {scenario.id}")
        self.stdout.write(f"Score mutuelle: {score.score}/100 ({score.health_level})")
