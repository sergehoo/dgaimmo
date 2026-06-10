"""Moteur de simulation de quotité cessible — barème officiel Côte d'Ivoire.

Conforme au barème de référence appliqué par les institutions financières
ivoiriennes (UEMOA). Calcule en une seule passe :

- la quotité cessible réglementaire (% du salaire net)
- la quotité disponible (après mensualités existantes)
- la capacité d'endettement
- le montant maximal finançable selon banque/taux/durée
- la décision d'éligibilité
- les recommandations d'optimisation
- la comparaison automatique avec les banques partenaires
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


# Barème officiel Côte d'Ivoire (par tranche de salaire net mensuel FCFA)
# Source : barème de référence des établissements financiers UEMOA.
CI_QUOTITE_BRACKETS = [
    (Decimal("200000"),  Decimal("35")),
    (Decimal("400000"),  Decimal("38")),
    (Decimal("600000"),  Decimal("42")),
    (Decimal("800000"),  Decimal("45")),
    (Decimal("1000000"), Decimal("48")),
    (Decimal("1500000"), Decimal("52")),
    (Decimal("2000000"), Decimal("55")),
]
CI_QUOTITE_DEFAULT = Decimal("57")  # > 2 000 000 FCFA


def quotite_rate_for_salary(net_salary: Decimal) -> Decimal:
    """Retourne le pourcentage officiel de quotité cessible pour un salaire net."""
    salary = Decimal(net_salary)
    for cap, rate in CI_QUOTITE_BRACKETS:
        if salary <= cap:
            return rate
    return CI_QUOTITE_DEFAULT


def quotite_bracket_label(net_salary: Decimal) -> str:
    """Libellé humain de la tranche du salaire."""
    salary = Decimal(net_salary)
    prev = Decimal("0")
    for cap, rate in CI_QUOTITE_BRACKETS:
        if salary <= cap:
            return f"{_fmt(prev)} < salaire ≤ {_fmt(cap)} FCFA → {rate} %"
        prev = cap
    return f"salaire > {_fmt(prev)} FCFA → {CI_QUOTITE_DEFAULT} %"


def _fmt(n: Decimal) -> str:
    return f"{int(n):,}".replace(",", " ")


def _monthly_payment(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    """Calcul de la mensualité d'un prêt amortissable classique."""
    principal = Decimal(principal or 0)
    months = int(months or 0)
    annual_rate = Decimal(annual_rate or 0)
    if months <= 0 or principal <= 0:
        return Decimal("0")
    if annual_rate == 0:
        return _round(principal / months)
    monthly_rate = annual_rate / Decimal("100") / Decimal("12")
    payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-months))
    return _round(payment)


def _financeable_amount(max_payment: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    """Inverse : montant finançable pour une mensualité maximum donnée."""
    max_payment = Decimal(max_payment or 0)
    months = int(months or 0)
    annual_rate = Decimal(annual_rate or 0)
    if months <= 0 or max_payment <= 0:
        return Decimal("0")
    if annual_rate == 0:
        return _round(max_payment * months)
    monthly_rate = annual_rate / Decimal("100") / Decimal("12")
    return _round(max_payment * (1 - (1 + monthly_rate) ** (-months)) / monthly_rate)


def _round(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _safe_sum(items: Iterable, key: str) -> Decimal:
    """Somme les valeurs `key` d'une liste de dicts en Decimal."""
    total = Decimal("0")
    for it in items or []:
        try:
            total += Decimal(str(it.get(key, 0) or 0).replace(",", "."))
        except Exception:
            continue
    return total


def compute_quotite_simulation(
    *,
    net_salary,
    additional_revenues=None,
    charges=None,
    credits=None,
    project_amount=None,
    personal_deposit=None,
    duration_months=240,
    annual_rate=None,
    bank=None,
    partner_banks=None,
):
    """Calcule la simulation complète de quotité cessible (Côte d'Ivoire).

    Args:
        net_salary: salaire net mensuel (FCFA).
        additional_revenues: list[{type, amount}].
        charges: list[{type, amount}].
        credits: list[{type, monthly_payment, remaining_months}].
        project_amount, personal_deposit, duration_months: paramètres projet.
        annual_rate: taux annuel si pas de banque sélectionnée.
        bank: dict {name, rate, max_months} sélectionnée → écrase annual_rate.
        partner_banks: list[{id, name, code, rate, max_months}] pour comparateur.

    Returns:
        dict structuré pour le dashboard frontend.
    """
    net_salary = Decimal(str(net_salary or 0).replace(",", "."))
    project_amount = Decimal(str(project_amount or 0).replace(",", "."))
    personal_deposit = Decimal(str(personal_deposit or 0).replace(",", "."))
    duration_months = int(duration_months or 240)

    # Taux retenu : celui de la banque sélectionnée prime
    if bank and bank.get("rate") is not None:
        effective_rate = Decimal(str(bank["rate"]))
    elif annual_rate is not None:
        effective_rate = Decimal(str(annual_rate).replace(",", "."))
    else:
        effective_rate = Decimal("7.5")  # défaut indicatif marché CI

    # ---- 1. Revenus ----
    additional_revenues_total = _safe_sum(additional_revenues, "amount")
    total_income = net_salary + additional_revenues_total

    # ---- 2. Charges ----
    charges_total = _safe_sum(charges, "amount")

    # ---- 3. Crédits existants ----
    existing_credits_total = _safe_sum(credits, "monthly_payment")

    # ---- 4. Quotité cessible réglementaire ----
    quotite_rate = quotite_rate_for_salary(net_salary)
    quotite_cessible = _round(net_salary * quotite_rate / Decimal("100"))

    # ---- 5. Quotité disponible (après crédits existants) ----
    quotite_available = max(quotite_cessible - existing_credits_total, Decimal("0"))

    # ---- 7. Capacité maximale de financement ----
    # Le projet est financé après déduction de l'apport personnel
    target_finance = max(project_amount - personal_deposit, Decimal("0"))
    estimated_payment = (
        _monthly_payment(target_finance, effective_rate, duration_months)
        if target_finance > 0 else Decimal("0")
    )
    max_finance = _financeable_amount(quotite_available, effective_rate, duration_months)

    # ---- 6. Reste à vivre ----
    # On retranche également la mensualité du projet pour refléter la situation
    # APRÈS l'octroi du nouveau crédit. Sans projet, c'est le reste à vivre actuel.
    living_remainder = (
        total_income - charges_total - existing_credits_total - estimated_payment
    )

    # ---- 8. Décision ----
    decision, decision_label, decision_tone = _build_decision(
        estimated_payment, quotite_available, living_remainder, total_income
    )

    # ---- 9. Recommandations IA ----
    recommendations = _build_recommendations(
        net_salary=net_salary,
        total_income=total_income,
        quotite_cessible=quotite_cessible,
        quotite_available=quotite_available,
        existing_credits_total=existing_credits_total,
        charges_total=charges_total,
        living_remainder=living_remainder,
        target_finance=target_finance,
        estimated_payment=estimated_payment,
        max_finance=max_finance,
        decision=decision,
        personal_deposit=personal_deposit,
        duration_months=duration_months,
    )

    # ---- 10. Analyse IA (texte narratif) ----
    ai_text = _build_ai_narrative(
        net_salary=net_salary,
        quotite_rate=quotite_rate,
        quotite_cessible=quotite_cessible,
        quotite_available=quotite_available,
        max_finance=max_finance,
        target_finance=target_finance,
        duration_months=duration_months,
        recommendations=recommendations,
    )

    # ---- 11. Comparateur de banques ----
    comparator = _build_bank_comparator(
        partner_banks=partner_banks or [],
        quotite_available=quotite_available,
        duration_months=duration_months,
        target_finance=target_finance,
    )

    # ---- 12. Décomposition pour graphiques ----
    breakdown = {
        "income": float(total_income),
        "charges": float(charges_total),
        "credits": float(existing_credits_total),
        "available_quotite": float(quotite_available),
        "living_remainder": float(max(living_remainder, Decimal("0"))),
    }

    return {
        "ok": True,
        # Inputs synthèse
        "net_salary": float(net_salary),
        "additional_revenues_total": float(additional_revenues_total),
        "total_income": float(total_income),
        "charges_total": float(charges_total),
        "existing_credits_total": float(existing_credits_total),
        # Cœur réglementaire
        "quotite_rate": float(quotite_rate),
        "quotite_bracket_label": quotite_bracket_label(net_salary),
        "quotite_cessible": float(quotite_cessible),
        "quotite_available": float(quotite_available),
        # Capacité
        "living_remainder": float(living_remainder),
        "max_finance": float(max_finance),
        "estimated_payment": float(estimated_payment),
        "target_finance": float(target_finance),
        "effective_rate": float(effective_rate),
        "duration_months": duration_months,
        # Jauge dynamique (0–57 %)
        "gauge": {
            "value": float(quotite_rate),
            "max": 57,
            "position_pct": float((quotite_rate / Decimal("57")) * 100),
        },
        # Décision
        "decision": decision,
        "decision_label": decision_label,
        "decision_tone": decision_tone,
        # IA
        "recommendations": recommendations,
        "ai_text": ai_text,
        # Comparateur
        "comparator": comparator,
        # Données graphiques
        "breakdown": breakdown,
    }


def _build_decision(estimated_payment, quotite_available, living_remainder, total_income):
    if total_income == 0:
        return "rejected", "Non éligible", "red"
    if estimated_payment == 0:
        # Pas de projet saisi : on retourne juste la capacité indicative
        return "info", "Capacité estimée", "indigo"
    if estimated_payment <= quotite_available and living_remainder > total_income * Decimal("0.35"):
        return "eligible", "Projet finançable", "green"
    if estimated_payment <= quotite_available * Decimal("1.10") and living_remainder > 0:
        return "conditional", "Projet réalisable sous réserve d'ajustements", "amber"
    return "rejected", "Projet actuellement non compatible", "red"


def _build_recommendations(**ctx):
    """Heuristiques d'optimisation du dossier."""
    recs = []
    if ctx["estimated_payment"] > ctx["quotite_available"] and ctx["quotite_available"] > 0:
        gap = ctx["estimated_payment"] - ctx["quotite_available"]
        recs.append(
            f"Vous dépassez la quotité disponible de {_fmt(gap)} FCFA. "
            "Augmentez l'apport personnel ou allongez la durée."
        )
    if ctx["existing_credits_total"] > ctx["net_salary"] * Decimal("0.20"):
        recs.append(
            "Vos crédits en cours dépassent 20 % de votre salaire net. "
            "Solder ou regrouper certains crédits libérerait votre quotité disponible."
        )
    if ctx["personal_deposit"] == 0 and ctx["target_finance"] > 0:
        suggested = ctx["target_finance"] * Decimal("0.20")
        recs.append(
            f"Aucun apport personnel n'est saisi. Un apport de {_fmt(suggested)} FCFA "
            "(20 %) améliorerait significativement votre décision et votre mensualité."
        )
    if ctx["duration_months"] < 240 and ctx["decision"] != "eligible" and ctx["target_finance"] > 0:
        recs.append(
            "Allonger la durée à 20 ans (240 mois) peut réduire la mensualité "
            "et débloquer l'éligibilité."
        )
    if ctx["living_remainder"] < ctx["total_income"] * Decimal("0.30"):
        recs.append(
            "Votre reste à vivre est inférieur à 30 % du revenu global. "
            "Prévoyez une marge de sécurité avant d'augmenter votre endettement."
        )
    if ctx["max_finance"] > 0 and ctx["target_finance"] > 0 and ctx["target_finance"] > ctx["max_finance"]:
        recs.append(
            f"Votre capacité maximale est {_fmt(ctx['max_finance'])} FCFA. "
            "Réduisez le prix du bien ou complétez par un apport pour atteindre la cible."
        )
    if not recs:
        recs.append("Aucune optimisation urgente — dossier solide.")
    return recs


def _build_ai_narrative(**ctx):
    lines = [
        f"Votre salaire net de {_fmt(ctx['net_salary'])} FCFA vous place dans la tranche "
        f"de quotité cessible de {ctx['quotite_rate']} % (barème officiel Côte d'Ivoire), "
        f"soit {_fmt(ctx['quotite_cessible'])} FCFA.",
        f"Après prise en compte de vos crédits existants, votre quotité disponible est "
        f"de {_fmt(ctx['quotite_available'])} FCFA.",
        f"Sur une durée de {ctx['duration_months']} mois, vous pouvez financer "
        f"jusqu'à {_fmt(ctx['max_finance'])} FCFA.",
    ]
    if ctx["target_finance"] > 0:
        diff = ctx["target_finance"] - ctx["max_finance"]
        if diff > 0:
            lines.append(
                f"Pour atteindre votre cible de {_fmt(ctx['target_finance'])} FCFA, "
                f"il vous manque {_fmt(diff)} FCFA de capacité."
            )
        else:
            lines.append(
                f"Votre cible de {_fmt(ctx['target_finance'])} FCFA est compatible avec "
                "votre capacité actuelle."
            )
    if ctx["recommendations"]:
        lines.append("Recommandations :")
        for r in ctx["recommendations"]:
            lines.append(f"• {r}")
    return "\n".join(lines)


def _build_bank_comparator(*, partner_banks, quotite_available, duration_months, target_finance):
    """Construit le tableau de comparaison banque par banque."""
    rows = []
    for b in partner_banks:
        rate = b.get("rate")
        if rate is None:
            continue
        rate_dec = Decimal(str(rate))
        max_months = int(b.get("max_months") or duration_months)
        effective_months = min(duration_months, max_months)

        max_amount = _financeable_amount(quotite_available, rate_dec, effective_months)
        # Mensualité pour le projet visé si défini
        payment_for_target = (
            _monthly_payment(target_finance, rate_dec, effective_months)
            if target_finance > 0 else Decimal("0")
        )
        rows.append({
            "id": b.get("id"),
            "name": b.get("name"),
            "code": b.get("code"),
            "rate": float(rate_dec),
            "max_months": effective_months,
            "max_finance": float(max_amount),
            "payment_for_target": float(payment_for_target),
            "is_partner": b.get("is_partner", True),
        })
    if not rows:
        return {"rows": [], "best_rate_id": None, "best_finance_id": None, "best_payment_id": None}

    best_rate = min(rows, key=lambda r: r["rate"])
    best_finance = max(rows, key=lambda r: r["max_finance"])
    # Meilleure mensualité = la plus basse (pour le projet cible) parmi celles > 0
    payable = [r for r in rows if r["payment_for_target"] > 0]
    best_payment = min(payable, key=lambda r: r["payment_for_target"]) if payable else None

    return {
        "rows": rows,
        "best_rate_id": best_rate["id"],
        "best_finance_id": best_finance["id"],
        "best_payment_id": best_payment["id"] if best_payment else None,
    }
