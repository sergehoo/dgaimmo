from decimal import Decimal, ROUND_HALF_UP

from contributions.models import Contribution
from memberships.models import Member
from real_estate.models import (
    DebtCommitment,
    FinancingScenario,
    MemberCreditScore,
    MutuelleGlobalScore,
    QuotiteCessibleSimulation,
    RealEstateProgram,
    RealEstateProgramScore,
)
from treasury.models import CashAccount


TWOPLACES = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def monthly_payment(principal, annual_rate, months):
    principal = Decimal(principal)
    months = int(months)
    if months <= 0:
        return Decimal("0.00")
    monthly_rate = Decimal(annual_rate) / Decimal("100") / Decimal("12")
    if monthly_rate == 0:
        return money(principal / months)
    payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-months))
    return money(payment)


def financeable_amount(max_payment, annual_rate, months):
    max_payment = Decimal(max_payment)
    monthly_rate = Decimal(annual_rate) / Decimal("100") / Decimal("12")
    if monthly_rate == 0:
        return money(max_payment * months)
    amount = max_payment * (1 - (1 + monthly_rate) ** (-months)) / monthly_rate
    return money(amount)


def simulate_quotite(mutuelle, member, requested_amount, duration_months, annual_interest_rate=8, max_debt_ratio=33):
    profile = member.financial_profile
    existing_payment = sum(DebtCommitment.objects.filter(member=member).values_list("monthly_payment", flat=True))
    total_income = profile.total_income
    monthly_charges = profile.fixed_charges + profile.mutual_contributions
    max_authorized = total_income * Decimal(max_debt_ratio) / Decimal("100")
    estimated = monthly_payment(requested_amount, annual_interest_rate, duration_months)
    net_capacity = max_authorized - monthly_charges - existing_payment
    living_remainder = total_income - monthly_charges - existing_payment - estimated
    debt_ratio = Decimal("0.00") if total_income == 0 else ((monthly_charges + existing_payment + estimated) / total_income) * 100

    if estimated <= net_capacity and living_remainder > total_income * Decimal("0.35"):
        decision = QuotiteCessibleSimulation.Decision.ELIGIBLE
    elif estimated <= max_authorized and living_remainder > 0:
        decision = QuotiteCessibleSimulation.Decision.CONDITIONAL
    else:
        decision = QuotiteCessibleSimulation.Decision.REJECTED

    recommendations = []
    if debt_ratio > Decimal(max_debt_ratio):
        recommendations.append("Réduire le montant demandé ou allonger la durée.")
    if profile.dependents_count >= 4:
        recommendations.append("Prévoir un reste à vivre renforcé pour charges familiales.")
    if profile.employment_type in {"independent", "informal"}:
        recommendations.append("Exiger justificatifs de revenus récurrents et épargne préalable.")

    return QuotiteCessibleSimulation.all_objects.create(
        mutuelle=mutuelle,
        member=member,
        requested_amount=requested_amount,
        requested_duration_months=duration_months,
        annual_interest_rate=annual_interest_rate,
        max_debt_ratio=max_debt_ratio,
        total_income=money(total_income),
        monthly_charges=money(monthly_charges),
        existing_debt_payments=money(existing_payment),
        gross_capacity=money(max_authorized),
        net_capacity=money(max(net_capacity, Decimal("0"))),
        max_authorized_payment=money(max_authorized),
        estimated_payment=estimated,
        debt_ratio=money(debt_ratio),
        living_remainder=money(living_remainder),
        financeable_amount=financeable_amount(max(net_capacity, Decimal("0")), annual_interest_rate, duration_months),
        decision=decision,
        recommendations=recommendations,
    )


def compute_member_score(mutuelle, member):
    contributions = Contribution.objects.filter(member=member)
    total = contributions.count()
    paid = contributions.filter(status=Contribution.Status.PAID).count()
    regularity = 100 if total == 0 else int((paid / total) * 100)
    kyc = 15 if member.kyc_validated else 0
    financial = getattr(member, "financial_profile", None)
    income_points = min(int((financial.total_income if financial else 0) / 50000), 20)
    debt_points = 20
    if financial:
        debt_payment = sum(DebtCommitment.objects.filter(member=member).values_list("monthly_payment", flat=True))
        ratio = 0 if financial.total_income == 0 else (debt_payment / financial.total_income) * 100
        debt_points = max(0, 20 - int(ratio / 2))
    score = max(0, min(100, int(regularity * 0.35 + kyc + income_points + debt_points + 10)))
    level = "excellent" if score >= 85 else "bon" if score >= 70 else "moyen" if score >= 50 else "faible"
    obj, _ = MemberCreditScore.all_objects.update_or_create(
        mutuelle=mutuelle,
        member=member,
        defaults={
            "score": score,
            "level": level,
            "default_risk": money(max(0, 100 - score)),
            "max_recommended_amount": money(score * Decimal("100000")),
            "recommendations": ["Renforcer l'épargne préalable"] if score < 70 else ["Profil finançable sous contrôle standard"],
            "factors": {"regularity": regularity, "kyc": member.kyc_validated, "income_points": income_points},
        },
    )
    return obj


def compute_mutuelle_score(mutuelle):
    members = Member.objects.filter(mutuelle=mutuelle)
    total_members = members.count()
    active_members = members.filter(status=Member.Status.ACTIVE).count()
    paid_ratio = 0
    contributions = Contribution.objects.filter(mutuelle=mutuelle)
    if contributions.exists():
        paid_ratio = contributions.filter(status=Contribution.Status.PAID).count() / contributions.count()
    treasury = sum(CashAccount.objects.filter(mutuelle=mutuelle, active=True).values_list("balance", flat=True))
    treasury_score = min(float(treasury) / 1_000_000, 30)
    score = int(min(100, (active_members * 100 / max(total_members, 1)) * 0.35 + paid_ratio * 35 + treasury_score))
    health = "excellent" if score >= 85 else "solide" if score >= 70 else "stable" if score >= 55 else "fragile" if score >= 40 else "critique"
    obj, _ = MutuelleGlobalScore.all_objects.update_or_create(
        mutuelle=mutuelle,
        defaults={
            "score": score,
            "health_level": health,
            "max_collective_financing": money(treasury * Decimal("3.0")),
            "max_bank_guarantee": money(treasury * Decimal("1.5")),
            "risk_level": "low" if score >= 70 else "medium" if score >= 50 else "high",
            "recommendations": ["Améliorer la régularité des cotisations", "Diversifier les contributeurs clés"],
            "metrics": {"total_members": total_members, "active_members": active_members, "paid_ratio": paid_ratio, "treasury": str(treasury)},
        },
    )
    return obj


def compute_program_score(mutuelle, program: RealEstateProgram):
    checklist = program.documents_checklist or {}
    doc_score = sum(1 for value in checklist.values() if value) * 10
    developer_score = 20 if program.developer_id else 5
    legal_score = 20 if program.legal_status else 5
    demand_score = min(program.total_lots, 30)
    score = max(0, min(100, doc_score + developer_score + legal_score + demand_score))
    recommendation = "recommandé" if score >= 80 else "acceptable" if score >= 60 else "risqué" if score >= 40 else "à éviter"
    obj, _ = RealEstateProgramScore.all_objects.update_or_create(
        mutuelle=mutuelle,
        program=program,
        defaults={
            "score": score,
            "risk_level": "low" if score >= 70 else "medium" if score >= 50 else "high",
            "recommendation": recommendation,
            "ai_summary": "Synthèse à enrichir par le moteur IA hybride.",
            "checklist": checklist,
            "factors": {"documents": doc_score, "developer": developer_score, "legal": legal_score, "demand": demand_score},
        },
    )
    return obj


def create_financing_scenario(mutuelle, member, opportunity, mode, personal_deposit, duration_months, annual_interest_rate):
    principal = Decimal(opportunity.amount) - Decimal(personal_deposit)
    payment = monthly_payment(principal, annual_interest_rate, duration_months)
    plan = [{"month": i, "payment": str(payment)} for i in range(1, min(int(duration_months), 360) + 1)]
    return FinancingScenario.all_objects.create(
        mutuelle=mutuelle,
        member=member,
        opportunity=opportunity,
        mode=mode,
        property_price=opportunity.amount,
        personal_deposit=personal_deposit,
        principal=money(principal),
        annual_interest_rate=annual_interest_rate,
        duration_months=duration_months,
        monthly_payment=payment,
        total_cost=money(payment * Decimal(duration_months) + Decimal(personal_deposit)),
        repayment_plan=plan,
    )
