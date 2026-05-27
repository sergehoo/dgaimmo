from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from contributions.models import Contribution
from payments.models import Payment
from treasury.models import LedgerEntry


class MVPWorkflowAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_mutuelle_real_estate_mvp_workflow(self):
        bootstrap = self.client.post(
            "/api/v1/auth/bootstrap-mutuelle/",
            {
                "email": "admin@dga.test",
                "phone": "+2250700000001",
                "password": "StrongPass123",
                "first_name": "Serge",
                "last_name": "Admin",
                "mutuelle_name": "DGA Habitat",
                "country": "CI",
                "currency": "XOF",
            },
            format="json",
        )
        self.assertEqual(bootstrap.status_code, 201, bootstrap.data)
        token = bootstrap.data["access"]
        mutuelle_id = bootstrap.data["mutuelle"]["id"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_MUTUELLE_ID=str(mutuelle_id))

        member = self.client.post(
            "/api/v1/members/",
            {
                "member_code": "DGA-001",
                "first_name": "Awa",
                "last_name": "Kone",
                "phone": "+2250700000002",
                "qr_token": "qr-dga-001",
                "status": "active",
                "kyc_validated": True,
            },
            format="json",
        )
        self.assertEqual(member.status_code, 201, member.data)
        member_id = member.data["id"]

        profile = self.client.post(
            "/api/v1/real-estate/member-financial-profiles/",
            {
                "member": member_id,
                "net_monthly_salary": "650000.00",
                "complementary_income": "100000.00",
                "fixed_charges": "120000.00",
                "mutual_contributions": "25000.00",
                "dependents_count": 2,
                "employment_type": "public",
                "risk_level": "low",
            },
            format="json",
        )
        self.assertEqual(profile.status_code, 201, profile.data)

        contribution_plan = self.client.post(
            "/api/v1/contribution-plans/",
            {"name": "Mensuelle habitat", "frequency": "monthly", "amount": "25000.00", "active": True},
            format="json",
        )
        self.assertEqual(contribution_plan.status_code, 201, contribution_plan.data)

        contribution = self.client.post(
            "/api/v1/contributions/",
            {
                "member": member_id,
                "plan": contribution_plan.data["id"],
                "amount": "25000.00",
                "currency": "XOF",
                "due_date": "2026-06-01",
                "status": "due",
            },
            format="json",
        )
        self.assertEqual(contribution.status_code, 201, contribution.data)

        program = self.client.post(
            "/api/v1/real-estate/programs/",
            {"name": "Bingerville Habitat", "city": "Bingerville", "country": "CI", "total_lots": 20, "status": "active"},
            format="json",
        )
        self.assertEqual(program.status_code, 201, program.data)

        opportunity = self.client.post(
            "/api/v1/real-estate/opportunities/",
            {
                "program": program.data["id"],
                "title": "Villa F4 - Tranche 1",
                "property_type": "villa",
                "amount": "25000000.00",
                "currency": "XOF",
                "initial_deposit": "5000000.00",
                "financing_months": 120,
                "available_lots": 1,
                "status": "available",
            },
            format="json",
        )
        self.assertEqual(opportunity.status_code, 201, opportunity.data)

        lot = self.client.post(
            "/api/v1/real-estate/lots/",
            {
                "opportunity": opportunity.data["id"],
                "lot_number": "VILLA-A01",
                "surface_area": "120.00",
                "amount": "25000000.00",
                "currency": "XOF",
                "status": "available",
            },
            format="json",
        )
        self.assertEqual(lot.status_code, 201, lot.data)

        simulation = self.client.post(
            "/api/v1/real-estate/quotite-simulations/",
            {
                "member": member_id,
                "requested_amount": "20000000.00",
                "requested_duration_months": 120,
                "annual_interest_rate": "7.00",
                "max_debt_ratio": "33.00",
            },
            format="json",
        )
        self.assertEqual(simulation.status_code, 201, simulation.data)
        self.assertIn(simulation.data["decision"], ["eligible", "conditional", "rejected"])
        self.assertGreater(Decimal(simulation.data["financeable_amount"]), Decimal("0"))

        financing = self.client.post(
            f"/api/v1/real-estate/opportunities/{opportunity.data['id']}/simulate-financing/",
            {
                "member": member_id,
                "mode": "mutuelle_loan",
                "personal_deposit": "5000000.00",
                "duration_months": 120,
                "annual_interest_rate": "7.00",
            },
            format="json",
        )
        self.assertEqual(financing.status_code, 201, financing.data)
        self.assertEqual(financing.data["principal"], "20000000.00")

        reservation = self.client.post(
            "/api/v1/real-estate/reservations/",
            {"lot": lot.data["id"], "member": member_id, "status": "pending", "deposit_paid": "500000.00"},
            format="json",
        )
        self.assertEqual(reservation.status_code, 201, reservation.data)

        payment = self.client.post(
            "/api/v1/payments/mobile-money/initiate/",
            {
                "provider": "wave",
                "contribution": contribution.data["id"],
                "phone": "+2250700000002",
                "idempotency_key": "idem-dga-001",
            },
            format="json",
        )
        self.assertEqual(payment.status_code, 201, payment.data)
        self.assertEqual(payment.data["status"], Payment.Status.PENDING)
        self.assertTrue(payment.data["external_reference"].startswith("MM-WAV-"))

        duplicate_payment = self.client.post(
            "/api/v1/payments/mobile-money/initiate/",
            {
                "provider": "wave",
                "contribution": contribution.data["id"],
                "phone": "+2250700000002",
                "idempotency_key": "idem-dga-001",
            },
            format="json",
        )
        self.assertEqual(duplicate_payment.status_code, 201, duplicate_payment.data)
        self.assertEqual(duplicate_payment.data["id"], payment.data["id"])

        webhook = self.client.post(
            "/api/v1/payments/mobile-money/webhook/",
            {"reference": payment.data["external_reference"], "status": "success", "provider": "wave"},
            format="json",
        )
        self.assertEqual(webhook.status_code, 200, webhook.data)
        self.assertEqual(webhook.data["payment_status"], Payment.Status.SUCCESS)
        contribution_obj = Contribution.all_objects.get(id=contribution.data["id"])
        self.assertEqual(contribution_obj.status, Contribution.Status.PAID)
        self.assertTrue(contribution_obj.receipt_number.startswith("RCT-"))
        self.assertTrue(LedgerEntry.all_objects.filter(reference=payment.data["external_reference"]).exists())

        dashboard = self.client.get("/api/v1/real-estate/scores/dashboard/")
        self.assertEqual(dashboard.status_code, 200, dashboard.data)
        self.assertIn("available_opportunities", dashboard.data)
