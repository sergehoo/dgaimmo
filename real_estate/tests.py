from decimal import Decimal

from django.test import TestCase

from memberships.models import Member
from mutuelles.models import Mutuelle
from real_estate.models import MemberFinancialProfile, RealEstateOpportunity, RealEstateProgram
from real_estate.services import create_financing_scenario, monthly_payment, simulate_quotite


class RealEstateFinanceTests(TestCase):
    def setUp(self):
        self.mutuelle = Mutuelle.objects.create(name="DGA Mutuelle", slug="dga", country="CI", currency="XOF")
        self.member = Member.all_objects.create(
            mutuelle=self.mutuelle,
            member_code="MX-001",
            first_name="Awa",
            last_name="Kone",
            phone="+2250700000000",
            qr_token="qr-awa-001",
            status=Member.Status.ACTIVE,
            kyc_validated=True,
        )
        MemberFinancialProfile.all_objects.create(
            mutuelle=self.mutuelle,
            member=self.member,
            net_monthly_salary=Decimal("650000"),
            complementary_income=Decimal("100000"),
            fixed_charges=Decimal("120000"),
            mutual_contributions=Decimal("25000"),
            dependents_count=2,
            employment_type=MemberFinancialProfile.EmploymentType.PUBLIC,
        )

    def test_monthly_payment_is_computed(self):
        payment = monthly_payment(Decimal("12000000"), Decimal("8"), 120)
        self.assertGreater(payment, Decimal("0"))
        self.assertEqual(payment.quantize(Decimal("0.01")), payment)

    def test_quotite_simulation_returns_financial_decision(self):
        simulation = simulate_quotite(self.mutuelle, self.member, Decimal("12000000"), 120, 8, 33)
        self.assertIn(simulation.decision, {"eligible", "conditional", "rejected"})
        self.assertGreater(simulation.total_income, Decimal("0"))
        self.assertGreaterEqual(simulation.financeable_amount, Decimal("0"))

    def test_financing_scenario_builds_repayment_plan(self):
        program = RealEstateProgram.all_objects.create(mutuelle=self.mutuelle, name="Bingerville Habitat", total_lots=30)
        opportunity = RealEstateOpportunity.all_objects.create(
            mutuelle=self.mutuelle,
            program=program,
            title="Villa F4",
            property_type=RealEstateOpportunity.PropertyType.VILLA,
            amount=Decimal("25000000"),
            currency="XOF",
        )
        scenario = create_financing_scenario(self.mutuelle, self.member, opportunity, "mutuelle_loan", Decimal("5000000"), 120, 7)
        self.assertEqual(scenario.principal, Decimal("20000000.00"))
        self.assertEqual(len(scenario.repayment_plan), 120)
