from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.db import models, transaction
from django.db.models import Avg, Sum
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import csv
import json
import uuid

from ai_engine.models import AIAnalysis
from ai_engine.services import generate_mutuelle_decision_note
from accounts.models import LoginEvent, OTPChallenge, UserDevice
from accounts.services import create_otp_challenge, record_login_event, upsert_user_device, verify_otp_challenge
from claims.models import AssistanceClaim
from claims.services import advance_claim
from contributions.models import Contribution, ContributionPlan
from core.models import TenantQuota
from dashboard.forms import (
    FinancialProfileForm,
    AIAnalysisCreateForm,
    AssistanceClaimCreateForm,
    FinancingScenarioCreateForm,
    GeneralAssemblyCreateForm,
    MFARequestForm,
    MFAVerifyForm,
    NotificationCreateForm,
    ResolutionCreateForm,
    MutuelleBrandingForm,
    ContributionCreateForm,
    ContributionPlanCreateForm,
    MemberCreateForm,
    MutuelleCreateForm,
    PaymentCreateForm,
    PropertyDocumentUploadForm,
    ProjectCreateForm,
    PublicMutuelleSignupForm,
    ReservationCreateForm,
    SimulationCreateForm,
    UserPasswordChangeForm,
    UserProfileForm,
)
from governance.models import GeneralAssembly, Resolution, ResolutionVote
from memberships.models import Member
from mutuelles.models import Mutuelle, MutuelleMembership
from notifications.models import Notification
from notifications.services import queue_notification
from payments.models import Payment
from payments.services import initiate_mobile_money_payment, process_mobile_money_webhook
from reports.pdf import contribution_receipt_pdf, mutuelle_health_report_pdf
from real_estate.models import (
    FinancingScenario,
    MemberFinancialProfile,
    MortgageApplication,
    PropertyDocument,
    PropertyLot,
    PropertyReservation,
    QuotiteCessibleSimulation,
    RealEstateOpportunity,
    RealEstateProgram,
)
from real_estate.services import compute_mutuelle_score, compute_program_score, create_financing_scenario, simulate_quotite
from real_estate.tasks import process_property_document_ocr
from treasury.models import CashAccount


class SecureLoginView(LoginView):
    """Vue de connexion MutuelleX.

    - Si l'utilisateur est déjà authentifié, redirige immédiatement vers
      ``LOGIN_REDIRECT_URL`` (= ``dashboard-home``) au lieu d'afficher le
      formulaire (``redirect_authenticated_user``).
    - Enregistre un événement de connexion (succès / échec) dans LoginEvent
      pour l'audit trail.
    - Pose un cookie ``dga_device_id`` httpOnly pour le suivi d'appareil.
    """

    template_name = "dashboard/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        record_login_event(self.request, LoginEvent.Status.SUCCESS, user=user)
        response = super().form_valid(form)
        device = upsert_user_device(self.request, user, trusted=False)
        response.set_cookie("dga_device_id", device.device_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
        return response

    def form_invalid(self, form):
        email = self.request.POST.get("username", "")
        record_login_event(self.request, LoginEvent.Status.FAILED, email=email, metadata={"errors": form.errors.get_json_data()})
        return super().form_invalid(form)


def _active_mutuelle(request):
    """Résolution robuste de la mutuelle active pour l'utilisateur courant.

    Ordre de résolution :
    1. ``request.mutuelle`` (posée par ``ActiveTenantMiddleware`` depuis le
       header ``X-Mutuelle-ID`` ou ``request.user.default_mutuelle``).
    2. ``request.user.default_mutuelle`` (re-check explicite).
    3. Première ``MutuelleMembership`` active de l'utilisateur (admin prioritaire).
    4. Pour les superusers : première mutuelle ACTIVE en base.
    5. Sinon : ``None`` (l'appelant peut alors rediriger vers ``create-mutuelle``).

    Lors du fallback via membership ou superuser, on met à jour
    ``user.default_mutuelle`` pour que les requêtes suivantes soient cohérentes.
    """
    mutuelle = getattr(request, "mutuelle", None)
    user = getattr(request, "user", None)

    if not mutuelle and user is not None and user.is_authenticated:
        mutuelle = user.default_mutuelle

    if not mutuelle and user is not None and user.is_authenticated:
        # Fallback : memberships actifs de l'utilisateur, admin prioritaire
        membership = (
            MutuelleMembership.objects.filter(user=user, active=True)
            .select_related("mutuelle")
            .order_by(
                # priorité admin → autre rôle
                models.Case(models.When(role="admin", then=0), default=1),
                "created_at",
            )
            .first()
        )
        if membership:
            mutuelle = membership.mutuelle

    if not mutuelle and user is not None and user.is_authenticated and user.is_superuser:
        # Superuser sans rattachement : on lui donne la première mutuelle active
        mutuelle = Mutuelle.objects.filter(status=Mutuelle.Status.ACTIVE).order_by("created_at").first()

    # Persiste la mutuelle résolue comme default pour les prochaines requêtes
    if (
        mutuelle
        and user is not None
        and user.is_authenticated
        and not user.default_mutuelle_id
    ):
        user.default_mutuelle = mutuelle
        user.save(update_fields=["default_mutuelle"])

    return mutuelle


@transaction.atomic
def public_mutuelle_signup(request):
    if request.user.is_authenticated:
        return redirect("create-mutuelle")
    form = PublicMutuelleSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        mutuelle, user = form.save()
        MutuelleMembership.objects.create(mutuelle=mutuelle, user=user, role="admin", permissions=["*"], active=True)
        TenantQuota.objects.get_or_create(mutuelle=mutuelle)
        record_login_event(request, LoginEvent.Status.SUCCESS, user=user, metadata={"source": "public_mutuelle_signup"})
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        upsert_user_device(request, user, trusted=False)
        return redirect("mutuelle-detail", mutuelle_id=mutuelle.id)
    return render(request, "dashboard/signup_mutuelle.html", {"form": form})


def _tenant_theme(mutuelle=None):
    active_mutuelle = mutuelle or Mutuelle.objects.filter(status=Mutuelle.Status.ACTIVE).order_by("created_at").first()
    return {
        "active_mutuelle": active_mutuelle,
        "tenant_primary_color": (active_mutuelle.primary_color if active_mutuelle else "#0b55d9") or "#0b55d9",
        "tenant_accent_color": (active_mutuelle.accent_color if active_mutuelle else "#0bbf63") or "#0bbf63",
    }


def _mutuelle_context(mutuelle):
    context = {
        "mutuelle": mutuelle,
        "active_members": 0,
        "treasury_balance": 0,
        "collective_capacity": 0,
        "score": None,
        "opportunities": [],
        "programs_count": 0,
        "reservations_count": 0,
        "recent_simulations": [],
        "quotite_members_rows": [],
        "quotite_mutuelle_monthly_capacity": 0,
        "quotite_mutuelle_net_capacity": 0,
        "quotite_mutuelle_financeable_amount": 0,
        "quotite_mutuelle_living_remainder": 0,
        "quotite_mutuelle_avg_debt_ratio": 0,
        "quotite_mutuelle_avg_amortization_months": 0,
        "quotite_simulated_members_count": 0,
        "quotite_eligible_members_count": 0,
        "quotite_conditional_members_count": 0,
        "quotite_rejected_members_count": 0,
        "quotite_member_names": "[]",
        "quotite_member_capacities": "[]",
        "chart_labels": ["Nov", "Déc", "Jan", "Fév", "Mar", "Avr"],
        "chart_contributions": [0, 0, 0, 0, 0, 0],
        "chart_financing": [0, 0, 0, 0, 0, 0],
    }
    context.update(_tenant_theme(mutuelle))
    if not mutuelle:
        return context

    context["active_members"] = Member.all_objects.filter(mutuelle=mutuelle, status=Member.Status.ACTIVE).count()
    context["treasury_balance"] = CashAccount.all_objects.filter(mutuelle=mutuelle, active=True).aggregate(total=Sum("balance"))["total"] or 0
    score = compute_mutuelle_score(mutuelle)
    context["score"] = score
    context["collective_capacity"] = score.max_collective_financing
    context["opportunities"] = RealEstateOpportunity.all_objects.filter(mutuelle=mutuelle).select_related("program").order_by("-score")[:5]
    context["programs_count"] = RealEstateProgram.all_objects.filter(mutuelle=mutuelle).count()
    context["reservations_count"] = PropertyReservation.all_objects.filter(mutuelle=mutuelle).count()
    context["recent_simulations"] = QuotiteCessibleSimulation.all_objects.filter(mutuelle=mutuelle).select_related("member").order_by("-created_at")[:5]
    members = list(Member.all_objects.filter(mutuelle=mutuelle).order_by("last_name", "first_name"))
    latest_simulations = {}
    for simulation in (
        QuotiteCessibleSimulation.all_objects.filter(mutuelle=mutuelle)
        .select_related("member")
        .order_by("-created_at")
    ):
        latest_simulations.setdefault(simulation.member_id, simulation)

    quotite_rows = []
    for member in members:
        simulation = latest_simulations.get(member.id)
        quotite_rows.append(
            {
                "member": member,
                "simulation": simulation,
                "max_authorized_payment": simulation.max_authorized_payment if simulation else 0,
                "net_capacity": simulation.net_capacity if simulation else 0,
                "financeable_amount": simulation.financeable_amount if simulation else 0,
                "living_remainder": simulation.living_remainder if simulation else 0,
                "debt_ratio": simulation.debt_ratio if simulation else 0,
                "amortization_months": simulation.requested_duration_months if simulation else 0,
                "decision": simulation.get_decision_display() if simulation else "À simuler",
                "decision_code": simulation.decision if simulation else "missing",
            }
        )
    simulated_rows = [row for row in quotite_rows if row["simulation"]]
    context["quotite_members_rows"] = quotite_rows[:12]
    context["quotite_mutuelle_monthly_capacity"] = sum(row["max_authorized_payment"] for row in simulated_rows) or 0
    context["quotite_mutuelle_net_capacity"] = sum(row["net_capacity"] for row in simulated_rows) or 0
    context["quotite_mutuelle_financeable_amount"] = sum(row["financeable_amount"] for row in simulated_rows) or 0
    context["quotite_mutuelle_living_remainder"] = sum(row["living_remainder"] for row in simulated_rows) or 0
    context["quotite_mutuelle_avg_amortization_months"] = int(
        sum(row["amortization_months"] for row in simulated_rows) / len(simulated_rows)
    ) if simulated_rows else 0
    context["quotite_simulated_members_count"] = len(simulated_rows)
    context["quotite_eligible_members_count"] = len(
        [row for row in simulated_rows if row["decision_code"] == QuotiteCessibleSimulation.Decision.ELIGIBLE]
    )
    context["quotite_conditional_members_count"] = len(
        [row for row in simulated_rows if row["decision_code"] == QuotiteCessibleSimulation.Decision.CONDITIONAL]
    )
    context["quotite_rejected_members_count"] = len(
        [row for row in simulated_rows if row["decision_code"] == QuotiteCessibleSimulation.Decision.REJECTED]
    )
    context["quotite_mutuelle_avg_debt_ratio"] = int(
        sum(row["debt_ratio"] for row in simulated_rows) / len(simulated_rows)
    ) if simulated_rows else 0
    chart_rows = sorted(simulated_rows, key=lambda row: row["max_authorized_payment"], reverse=True)[:8]
    context["quotite_member_names"] = json.dumps([str(row["member"]) for row in chart_rows])
    context["quotite_member_capacities"] = json.dumps([int(row["max_authorized_payment"]) for row in chart_rows])
    paid_total = Contribution.all_objects.filter(mutuelle=mutuelle, status=Contribution.Status.PAID).aggregate(total=Sum("amount"))["total"] or 0
    contribution_factors = [Decimal("0.15"), Decimal("0.25"), Decimal("0.38"), Decimal("0.55"), Decimal("0.78"), Decimal("1")]
    financing_factors = [Decimal("0.20"), Decimal("0.32"), Decimal("0.48"), Decimal("0.63"), Decimal("0.80"), Decimal("1")]
    context["chart_contributions"] = [int(paid_total * factor / Decimal("1000000")) for factor in contribution_factors]
    context["chart_financing"] = [int(context["collective_capacity"] * factor / Decimal("1000000")) for factor in financing_factors]
    return context


def _global_context():
    mutuelles = Mutuelle.objects.all().order_by("name")
    active_mutuelle = Mutuelle.objects.filter(status=Mutuelle.Status.ACTIVE).order_by("created_at").first()
    members_count = Member.all_objects.count()
    active_members_count = Member.all_objects.filter(status=Member.Status.ACTIVE).count()
    programs_count = RealEstateProgram.all_objects.count()
    financing_total = CashAccount.all_objects.filter(active=True).aggregate(total=Sum("balance"))["total"] or 0
    paid_contributions_total = (
        Contribution.all_objects.filter(status=Contribution.Status.PAID).aggregate(total=Sum("amount"))["total"] or 0
    )
    due_contributions_count = Contribution.all_objects.filter(
        status__in=[Contribution.Status.DUE, Contribution.Status.PARTIAL, Contribution.Status.OVERDUE]
    ).count()
    overdue_contributions_count = Contribution.all_objects.filter(status=Contribution.Status.OVERDUE).count()
    mobile_money_success_count = Payment.all_objects.filter(status=Payment.Status.SUCCESS).count()
    mobile_money_pending_count = Payment.all_objects.filter(
        status__in=[Payment.Status.INITIATED, Payment.Status.PENDING]
    ).count()
    mobile_money_total = Payment.all_objects.filter(status=Payment.Status.SUCCESS).aggregate(total=Sum("amount"))["total"] or 0
    claims_open_count = AssistanceClaim.all_objects.exclude(
        status__in=[AssistanceClaim.Status.CLOSED, AssistanceClaim.Status.REJECTED]
    ).count()
    claims_review_count = AssistanceClaim.all_objects.filter(
        status__in=[AssistanceClaim.Status.SUBMITTED, AssistanceClaim.Status.REVIEW]
    ).count()
    claims_paid_total = (
        AssistanceClaim.all_objects.filter(status__in=[AssistanceClaim.Status.PAID, AssistanceClaim.Status.CLOSED]).aggregate(
            total=Sum("approved_amount")
        )["total"]
        or 0
    )
    documents_verified_count = PropertyDocument.all_objects.filter(verified=True).count()
    documents_pending_count = PropertyDocument.all_objects.filter(verified=False).count()
    documents_total = documents_verified_count + documents_pending_count
    ocr_confidence_avg = int((documents_verified_count / documents_total) * 100) if documents_total else 0
    simulations_eligible_count = QuotiteCessibleSimulation.all_objects.filter(
        decision=QuotiteCessibleSimulation.Decision.ELIGIBLE
    ).count()
    simulations_conditional_count = QuotiteCessibleSimulation.all_objects.filter(
        decision=QuotiteCessibleSimulation.Decision.CONDITIONAL
    ).count()
    simulations_rejected_count = QuotiteCessibleSimulation.all_objects.filter(
        decision=QuotiteCessibleSimulation.Decision.REJECTED
    ).count()
    reservations_count = PropertyReservation.all_objects.count()
    approved_reservations_count = PropertyReservation.all_objects.filter(
        status__in=[PropertyReservation.Status.APPROVED, PropertyReservation.Status.CONVERTED]
    ).count()
    available_lots_count = PropertyLot.all_objects.filter(status=PropertyLot.Status.AVAILABLE).count()
    financing_scenarios_count = FinancingScenario.all_objects.count()
    mortgage_applications_count = MortgageApplication.all_objects.count()
    mortgage_approved_count = MortgageApplication.all_objects.filter(
        status__in=[MortgageApplication.Status.APPROVED, MortgageApplication.Status.DISBURSED, MortgageApplication.Status.CLOSED]
    ).count()
    mortgage_disbursed_total = MortgageApplication.all_objects.aggregate(total=Sum("disbursed_amount"))["total"] or 0
    security_failed_logins = LoginEvent.objects.filter(status=LoginEvent.Status.FAILED).count()
    security_success_logins = LoginEvent.objects.filter(status=LoginEvent.Status.SUCCESS).count()
    ai_analyses_count = AIAnalysis.all_objects.count()
    notifications_queued_count = Notification.all_objects.filter(status=Notification.Status.QUEUED).count()
    rows = []
    for mutuelle in mutuelles:
        score = compute_mutuelle_score(mutuelle)
        rows.append(
            {
                "mutuelle": mutuelle,
                "members": Member.all_objects.filter(mutuelle=mutuelle).count(),
                "capacity": score.max_collective_financing,
                "score": score.score,
                "health": score.health_level,
                "last_activity": mutuelle.updated_at,
            }
        )
    operational_kpis = [
        {
            "label": "Cotisations encaissées",
            "value": paid_contributions_total,
            "suffix": "FCFA",
            "tone": "green",
            "detail": f"{due_contributions_count} échéances à suivre",
        },
        {
            "label": "Paiements Mobile Money",
            "value": mobile_money_total,
            "suffix": "FCFA",
            "tone": "blue",
            "detail": f"{mobile_money_success_count} réussis",
        },
        {
            "label": "Prestations ouvertes",
            "value": claims_open_count,
            "suffix": "",
            "tone": "amber",
            "detail": f"{claims_paid_total:,.0f} FCFA payés".replace(",", " "),
        },
        {
            "label": "Documents validés",
            "value": documents_verified_count,
            "suffix": "",
            "tone": "violet",
            "detail": f"{documents_pending_count} à contrôler",
        },
        {
            "label": "Membres actifs",
            "value": active_members_count,
            "suffix": "",
            "tone": "green",
            "detail": "Mutualistes opérationnels",
        },
        {
            "label": "Réservations lots",
            "value": reservations_count,
            "suffix": "",
            "tone": "blue",
            "detail": f"{approved_reservations_count} confirmées",
        },
        {
            "label": "Dossiers financement",
            "value": mortgage_applications_count,
            "suffix": "",
            "tone": "indigo",
            "detail": f"{mortgage_approved_count} approuvés",
        },
        {
            "label": "Analyses IA",
            "value": ai_analyses_count,
            "suffix": "",
            "tone": "slate",
            "detail": "Synthèses et scoring",
        },
    ]
    risk_watchlist = [
        {"label": "Cotisations en retard", "value": overdue_contributions_count, "level": "Critique"},
        {"label": "Paiements en attente", "value": mobile_money_pending_count, "level": "Flux"},
        {"label": "Prestations en analyse", "value": claims_review_count, "level": "Comité"},
        {"label": "Documents non validés", "value": documents_pending_count, "level": "KYC"},
        {"label": "Connexions échouées", "value": security_failed_logins, "level": "Sécurité"},
        {"label": "Notifications en file", "value": notifications_queued_count, "level": "Relance"},
    ]
    context = {
        "mutuelles": mutuelles,
        "mutuelle_rows": rows,
        "mutuelles_count": mutuelles.count(),
        "members_count": members_count,
        "active_members_count": active_members_count,
        "programs_count": programs_count,
        "financing_total": financing_total,
        "paid_contributions_total": paid_contributions_total,
        "due_contributions_count": due_contributions_count,
        "overdue_contributions_count": overdue_contributions_count,
        "mobile_money_success_count": mobile_money_success_count,
        "mobile_money_pending_count": mobile_money_pending_count,
        "mobile_money_total": mobile_money_total,
        "claims_open_count": claims_open_count,
        "claims_review_count": claims_review_count,
        "claims_paid_total": claims_paid_total,
        "documents_verified_count": documents_verified_count,
        "documents_pending_count": documents_pending_count,
        "ocr_confidence_avg": int(ocr_confidence_avg),
        "simulations_eligible_count": simulations_eligible_count,
        "simulations_conditional_count": simulations_conditional_count,
        "simulations_rejected_count": simulations_rejected_count,
        "reservations_count": reservations_count,
        "approved_reservations_count": approved_reservations_count,
        "available_lots_count": available_lots_count,
        "financing_scenarios_count": financing_scenarios_count,
        "mortgage_applications_count": mortgage_applications_count,
        "mortgage_approved_count": mortgage_approved_count,
        "mortgage_disbursed_total": mortgage_disbursed_total,
        "security_failed_logins": security_failed_logins,
        "security_success_logins": security_success_logins,
        "ai_analyses_count": ai_analyses_count,
        "notifications_queued_count": notifications_queued_count,
        "operational_kpis": operational_kpis,
        "risk_watchlist": risk_watchlist,
        "recent_payments": Payment.all_objects.select_related("member", "mutuelle").order_by("-created_at")[:5],
        "recent_claims": AssistanceClaim.all_objects.select_related("member", "mutuelle").order_by("-created_at")[:5],
        "recent_applications": MortgageApplication.all_objects.select_related(
            "member", "mutuelle", "scenario", "scenario__opportunity"
        ).order_by("-created_at")[:5],
    }
    context.update(_tenant_theme(active_mutuelle))
    return context


def landing_page(request):
    context = _global_context()
    return render(request, "dashboard/landing.html", context)


@login_required
def console_dashboard(request):
    context = _global_context()
    context.update(_mutuelle_context(_active_mutuelle(request)))
    context["active_tab"] = "dashboard"
    return render(request, "dashboard/console.html", context)


@login_required
def mutuelles_list(request):
    context = _global_context()
    context["active_tab"] = "mutuelles"
    return render(request, "dashboard/mutuelles_list.html", context)


# Iconographie + palette par type d'objectif immobilier (FontAwesome 6)
OBJECTIVE_ICON_MAP = {
    "terrain":                  ("fa-solid fa-map",                "#b56a00", "#fff4e5"),
    "maison":                   ("fa-solid fa-house-chimney",      "#0aa25f", "#e8fff2"),
    "immeuble":                 ("fa-solid fa-building",           "#0b55d9", "#eaf2ff"),
    "appartement":              ("fa-solid fa-city",               "#7c3aed", "#ede9fe"),
    "logement_social":          ("fa-solid fa-hand-holding-heart", "#c93838", "#ffecec"),
    "programme_promoteur":      ("fa-solid fa-handshake-angle",    "#06337d", "#dce8f8"),
    "construction_collective":  ("fa-solid fa-people-group",       "#0aa25f", "#caff3d"),
    "autre":                    ("fa-solid fa-circle-question",    "#536484", "#f3f7ff"),
}


def _aggregate_member_objectives(mutuelle):
    """Agrège les objectifs immobiliers déclarés par les membres d'une mutuelle.

    Retourne une liste ordonnée :
        [{'code', 'label', 'count', 'pct', 'icon', 'color', 'bg'}, ...]
    triée par nombre décroissant. Utile pour piloter le choix de programmes
    immobiliers : on voit instantanément ce que veut la majorité des membres.
    """
    from collections import Counter

    counter = Counter()
    for values in Member.all_objects.filter(mutuelle=mutuelle).values_list(
        "real_estate_objective", flat=True
    ):
        if values:
            counter.update(values)

    total_members = Member.all_objects.filter(mutuelle=mutuelle).count() or 1
    label_map = dict(Mutuelle.RealEstateObjective.choices)
    rows = []
    for code, count in counter.items():
        icon, color, bg = OBJECTIVE_ICON_MAP.get(
            code, ("fa-solid fa-bullseye", "#0b55d9", "#eaf2ff")
        )
        rows.append(
            {
                "code": code,
                "label": label_map.get(code, code),
                "count": count,
                "pct": round(count * 100 / total_members, 1),
                "icon": icon,
                "color": color,
                "bg": bg,
            }
        )
    return sorted(rows, key=lambda row: row["count"], reverse=True)


@login_required
def mutuelle_detail(request, mutuelle_id):
    """Page de détail d'une mutuelle.

    KPI affichés :
    1. Nombre de membres
    2. Capacité d'emprunt totale (somme des mensualités max autorisées des membres)
    3. Score de solvabilité global (MutuelleGlobalScore)
    4. Budget estimé du projet possible (financement collectif maximum)

    Sections :
    - Membres (avec banque et fonction)
    - Analyse financière (quotité cessible + cotisations)
    - Projets proposés (opportunités immobilières)
    - Suivi des paiements (paiements & cotisations récentes)
    - Documents
    """
    mutuelle = get_object_or_404(Mutuelle, id=mutuelle_id)
    context = _mutuelle_context(mutuelle)
    context["active_tab"] = "mutuelles"

    members_qs = Member.all_objects.filter(mutuelle=mutuelle)
    contribution_qs = Contribution.all_objects.filter(mutuelle=mutuelle)
    payment_qs = Payment.all_objects.filter(mutuelle=mutuelle)
    claims_qs = AssistanceClaim.all_objects.filter(mutuelle=mutuelle)
    programs_qs = RealEstateProgram.all_objects.filter(mutuelle=mutuelle)
    opportunities_qs = RealEstateOpportunity.all_objects.filter(mutuelle=mutuelle)
    simulations_qs = QuotiteCessibleSimulation.all_objects.filter(mutuelle=mutuelle)
    documents_qs = PropertyDocument.all_objects.filter(mutuelle=mutuelle)
    applications_qs = MortgageApplication.all_objects.filter(mutuelle=mutuelle)

    members_total = members_qs.count()
    # Agrégation des objectifs immobiliers déclarés par les membres
    members_objectives = _aggregate_member_objectives(mutuelle)
    # KPI #2 : Capacité d'emprunt totale (mensualité cumulée déjà calculée dans _mutuelle_context)
    total_borrowing_capacity = context.get("quotite_mutuelle_monthly_capacity") or 0
    # KPI #4 : Budget estimé du projet possible = financement collectif max
    estimated_project_budget = context.get("collective_capacity") or context.get("quotite_mutuelle_financeable_amount") or 0
    # KPI #3 : Score de solvabilité global
    mutuelle_score = context.get("score")
    solvency_score = mutuelle_score.score if mutuelle_score else 0
    solvency_level = mutuelle_score.health_level if mutuelle_score else "À évaluer"

    context.update(
        {
            # ---- KPI principaux ----
            "kpi_members_count": members_total,
            "kpi_borrowing_capacity": total_borrowing_capacity,
            "kpi_solvency_score": solvency_score,
            "kpi_solvency_level": solvency_level,
            # ---- Objectifs cumulés des membres ----
            "members_objectives_aggregated": members_objectives,
            "members_objectives_total_picks": sum(row["count"] for row in members_objectives),
            "members_with_objective_count": members_qs.exclude(
                real_estate_objective__exact=[]
            ).count(),
            "kpi_project_budget": estimated_project_budget,

            # ---- Section Membres ----
            "members": members_qs.select_related("bank").order_by("last_name", "first_name")[:12],
            "members_total": members_total,
            "members_kyc_validated": members_qs.filter(kyc_validated=True).count(),
            "members_active": members_qs.filter(status=Member.Status.ACTIVE).count(),
            "members_delinquent": members_qs.filter(status=Member.Status.DELINQUENT).count(),

            # ---- Section Analyse financière ----
            "contributions_paid_total": contribution_qs.filter(status=Contribution.Status.PAID).aggregate(total=Sum("amount"))["total"] or 0,
            "contributions_due_count": contribution_qs.filter(status__in=[Contribution.Status.DUE, Contribution.Status.PARTIAL, Contribution.Status.OVERDUE]).count(),
            "contributions_overdue_count": contribution_qs.filter(status=Contribution.Status.OVERDUE).count(),
            "treasury_balance": context.get("treasury_balance", 0),
            "simulations_total": simulations_qs.count(),
            "simulations_eligible": simulations_qs.filter(decision=QuotiteCessibleSimulation.Decision.ELIGIBLE).count(),
            "simulations_conditional": simulations_qs.filter(decision=QuotiteCessibleSimulation.Decision.CONDITIONAL).count(),
            "simulations_rejected": simulations_qs.filter(decision=QuotiteCessibleSimulation.Decision.REJECTED).count(),

            # ---- Section Projets proposés ----
            "programs": programs_qs.order_by("-created_at")[:6],
            "programs_count": programs_qs.count(),
            "opportunities": opportunities_qs.select_related("program").order_by("-score", "-created_at")[:6],
            "available_lots": PropertyLot.all_objects.filter(mutuelle=mutuelle, status=PropertyLot.Status.AVAILABLE).count(),
            "approved_reservations": PropertyReservation.all_objects.filter(mutuelle=mutuelle, status__in=[PropertyReservation.Status.APPROVED, PropertyReservation.Status.CONVERTED]).count(),

            # ---- Section Suivi des paiements ----
            "payments_success_total": payment_qs.filter(status=Payment.Status.SUCCESS).aggregate(total=Sum("amount"))["total"] or 0,
            "payments_pending_count": payment_qs.filter(status__in=[Payment.Status.INITIATED, Payment.Status.PENDING]).count(),
            "payments_failed_count": payment_qs.filter(status=Payment.Status.FAILED).count() if hasattr(Payment.Status, "FAILED") else 0,
            "recent_contributions": contribution_qs.select_related("member", "plan").order_by("-created_at")[:8],
            "recent_payments": payment_qs.select_related("member").order_by("-created_at")[:8],
            "recent_claims": claims_qs.select_related("member").order_by("-created_at")[:5],
            "claims_open_count": claims_qs.exclude(status__in=[AssistanceClaim.Status.CLOSED, AssistanceClaim.Status.REJECTED]).count(),
            "claims_paid_total": claims_qs.filter(status__in=[AssistanceClaim.Status.PAID, AssistanceClaim.Status.CLOSED]).aggregate(total=Sum("approved_amount"))["total"] or 0,

            # ---- Section Documents ----
            "documents_total": documents_qs.count(),
            "documents_verified": documents_qs.filter(verified=True).count(),
            "documents_pending": documents_qs.filter(verified=False).count(),
            "recent_documents": documents_qs.order_by("-created_at")[:8],

            # ---- Bonus : dossiers financement ----
            "mortgage_applications": applications_qs.select_related("member", "scenario", "scenario__opportunity").order_by("-created_at")[:5],
            "mortgage_applications_count": applications_qs.count(),
            "mortgage_approved_count": applications_qs.filter(status__in=[MortgageApplication.Status.APPROVED, MortgageApplication.Status.DISBURSED, MortgageApplication.Status.CLOSED]).count(),
            "mortgage_disbursed_total": applications_qs.aggregate(total=Sum("disbursed_amount"))["total"] or 0,
        }
    )
    return render(request, "dashboard/mutuelle_detail.html", context)


@login_required
def projects_center(request):
    context = _global_context()
    context["active_tab"] = "projects"
    context["programs"] = RealEstateProgram.all_objects.select_related("mutuelle").order_by("-created_at")[:20]
    context["opportunities"] = RealEstateOpportunity.all_objects.select_related("mutuelle", "program").order_by("-score", "-created_at")[:20]
    return render(request, "dashboard/projects.html", context)


@login_required
def members_center(request):
    context = _global_context()
    context["active_tab"] = "members"
    context["members"] = Member.all_objects.select_related("mutuelle").order_by("-created_at")[:30]
    context["simulations"] = QuotiteCessibleSimulation.all_objects.select_related("member", "mutuelle").order_by("-created_at")[:8]
    return render(request, "dashboard/members.html", context)


@login_required
def simulations_center(request):
    context = _global_context()
    context["active_tab"] = "simulations"
    simulations_qs = QuotiteCessibleSimulation.all_objects.select_related("member", "mutuelle")
    context["simulations"] = simulations_qs.order_by("-created_at")[:30]
    context["eligible_count"] = simulations_qs.filter(decision=QuotiteCessibleSimulation.Decision.ELIGIBLE).count()
    context["conditional_count"] = simulations_qs.filter(decision=QuotiteCessibleSimulation.Decision.CONDITIONAL).count()
    context["rejected_count"] = simulations_qs.filter(decision=QuotiteCessibleSimulation.Decision.REJECTED).count()
    context["avg_amortization_months"] = int(simulations_qs.aggregate(avg=Avg("requested_duration_months"))["avg"] or 0)
    return render(request, "dashboard/simulations.html", context)


@login_required
def simulation_detail(request, simulation_id):
    """Fiche complète d'une simulation de quotité cessible."""
    simulation = get_object_or_404(
        QuotiteCessibleSimulation.all_objects.select_related(
            "member", "member__bank", "member__financial_profile", "mutuelle"
        ),
        id=simulation_id,
    )
    member = simulation.member
    mutuelle = simulation.mutuelle

    # Comparaison avec les autres simulations du même membre
    other_simulations = (
        QuotiteCessibleSimulation.all_objects.filter(member=member, mutuelle=mutuelle)
        .exclude(id=simulation.id)
        .order_by("-created_at")[:5]
    )

    context = _global_context()
    context.update(
        {
            "simulation": simulation,
            "member": member,
            "mutuelle": mutuelle,
            "active_mutuelle": mutuelle,
            "fin_profile": getattr(member, "financial_profile", None),
            "other_simulations": other_simulations,
            "active_tab": "simulations",
        }
    )
    return render(request, "dashboard/simulation_detail.html", context)


@login_required
def documents_center(request):
    context = _global_context()
    context["active_tab"] = "documents"
    context["documents"] = PropertyDocument.all_objects.select_related("mutuelle", "program").order_by("-created_at")[:20]
    context["verified_documents"] = PropertyDocument.all_objects.filter(verified=True).count()
    context["pending_documents"] = PropertyDocument.all_objects.filter(ocr_payload__status="queued").count()
    context["review_documents"] = PropertyDocument.all_objects.filter(ocr_payload__decision="review_required").count()
    return render(request, "dashboard/documents.html", context)


@login_required
def reports_center(request):
    context = _global_context()
    context["active_tab"] = "reports"
    return render(request, "dashboard/reports.html", context)


@login_required
def notifications_center(request):
    context = _global_context()
    context["active_tab"] = "notifications"
    context["notifications"] = Notification.all_objects.select_related("mutuelle", "member", "recipient_user").order_by("-created_at")[:40]
    context["queued_count"] = Notification.all_objects.filter(status=Notification.Status.QUEUED).count()
    context["sent_count"] = Notification.all_objects.filter(status=Notification.Status.SENT).count()
    context["failed_count"] = Notification.all_objects.filter(status=Notification.Status.FAILED).count()
    return render(request, "dashboard/notifications.html", context)


@login_required
def field_offline_center(request):
    context = _global_context()
    context["active_tab"] = "offline"
    context["field_members"] = Member.all_objects.select_related("mutuelle").order_by("-created_at")[:12]
    context["field_payments"] = Payment.all_objects.select_related("mutuelle", "member").order_by("-created_at")[:12]
    return render(request, "dashboard/offline.html", context)


@login_required
def ai_copilot_center(request):
    context = _global_context()
    context["active_tab"] = "ai"
    context["analyses"] = AIAnalysis.all_objects.select_related("mutuelle").order_by("-created_at")[:20]
    context["decision_notes"] = AIAnalysis.all_objects.filter(analysis_type="mutuelle_decision_note").count()
    context["fraud_notes"] = AIAnalysis.all_objects.filter(analysis_type="fraud_risk").count()
    context["ocr_notes"] = AIAnalysis.all_objects.filter(analysis_type="ocr_document").count()
    return render(request, "dashboard/ai_copilot.html", context)


@login_required
def governance_center(request):
    context = _global_context()
    context["active_tab"] = "governance"
    context["assemblies"] = GeneralAssembly.all_objects.select_related("mutuelle").order_by("-scheduled_at")[:20]
    context["resolutions"] = Resolution.all_objects.select_related("mutuelle", "assembly").order_by("-created_at")[:20]
    context["open_resolutions"] = Resolution.all_objects.filter(status=Resolution.Status.OPEN).count()
    context["votes_count"] = ResolutionVote.all_objects.count()
    context["closed_assemblies"] = GeneralAssembly.all_objects.filter(status=GeneralAssembly.Status.CLOSED).count()
    return render(request, "dashboard/governance.html", context)


@login_required
def branding_center(request):
    context = _global_context()
    context["active_tab"] = "branding"
    return render(request, "dashboard/branding.html", context)


@login_required
def security_center(request):
    context = _global_context()
    context["active_tab"] = "security"
    context["login_events"] = LoginEvent.objects.select_related("user").order_by("-created_at")[:40]
    context["devices"] = UserDevice.objects.select_related("user").order_by("-last_seen_at")[:30]
    context["otp_challenges"] = OTPChallenge.objects.select_related("user").order_by("-created_at")[:20]
    context["success_logins"] = LoginEvent.objects.filter(status=LoginEvent.Status.SUCCESS).count()
    context["failed_logins"] = LoginEvent.objects.filter(status=LoginEvent.Status.FAILED).count()
    context["mfa_users"] = LoginEvent.objects.filter(user__mfa_enabled=True).values("user").distinct().count()
    return render(request, "dashboard/security.html", context)


@login_required
def profile_center(request):
    profile_form = UserProfileForm(instance=request.user)
    password_form = UserPasswordChangeForm(request.user)
    profile_saved = False
    password_saved = False

    if request.method == "POST" and request.POST.get("form_kind") == "profile":
        profile_form = UserProfileForm(request.POST, instance=request.user)
        if profile_form.is_valid():
            profile_form.save()
            profile_saved = True

    if request.method == "POST" and request.POST.get("form_kind") == "password":
        password_form = UserPasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            password_saved = True

    context = _global_context()
    context.update(
        {
            "active_tab": "profile",
            "profile_form": profile_form,
            "password_form": password_form,
            "profile_saved": profile_saved,
            "password_saved": password_saved,
            "my_devices": UserDevice.objects.filter(user=request.user).order_by("-last_seen_at")[:10],
            "my_login_events": LoginEvent.objects.filter(user=request.user).order_by("-created_at")[:10],
        }
    )
    return render(request, "dashboard/profile.html", context)


@login_required
def finance_center(request):
    context = _global_context()
    context["active_tab"] = "finance"
    context["contributions"] = Contribution.all_objects.select_related("member", "mutuelle", "plan").order_by("-created_at")[:30]
    context["plans"] = ContributionPlan.all_objects.select_related("mutuelle").order_by("-created_at")[:12]
    context["payments"] = Payment.all_objects.select_related("member", "mutuelle").order_by("-created_at")[:20]
    context["cash_accounts"] = CashAccount.all_objects.select_related("mutuelle").order_by("mutuelle__name", "name")[:20]
    context["paid_contributions"] = Contribution.all_objects.filter(status=Contribution.Status.PAID).count()
    context["pending_payments"] = Payment.all_objects.filter(status=Payment.Status.PENDING).count()
    return render(request, "dashboard/finance.html", context)


@login_required
def financing_center(request):
    context = _global_context()
    context["active_tab"] = "financing"
    context["scenarios"] = FinancingScenario.all_objects.select_related("mutuelle", "member", "opportunity", "opportunity__program").order_by("-created_at")[:30]
    context["applications"] = MortgageApplication.all_objects.select_related("mutuelle", "member", "scenario", "scenario__opportunity").order_by("-created_at")[:30]
    context["committee_count"] = MortgageApplication.all_objects.filter(status=MortgageApplication.Status.COMMITTEE).count()
    context["bank_review_count"] = MortgageApplication.all_objects.filter(status=MortgageApplication.Status.BANK_REVIEW).count()
    context["approved_count"] = MortgageApplication.all_objects.filter(status=MortgageApplication.Status.APPROVED).count()
    context["disbursed_total"] = MortgageApplication.all_objects.aggregate(total=Sum("disbursed_amount"))["total"] or 0
    return render(request, "dashboard/financing.html", context)


@login_required
def claims_center(request):
    context = _global_context()
    context["active_tab"] = "claims"
    context["claims"] = AssistanceClaim.all_objects.select_related("mutuelle", "member").order_by("-created_at")[:40]
    context["submitted_count"] = AssistanceClaim.all_objects.filter(status=AssistanceClaim.Status.SUBMITTED).count()
    context["review_count"] = AssistanceClaim.all_objects.filter(status=AssistanceClaim.Status.REVIEW).count()
    context["approved_count"] = AssistanceClaim.all_objects.filter(status=AssistanceClaim.Status.APPROVED).count()
    context["paid_total"] = AssistanceClaim.all_objects.filter(status__in=[AssistanceClaim.Status.PAID, AssistanceClaim.Status.CLOSED]).aggregate(total=Sum("approved_amount"))["total"] or 0
    return render(request, "dashboard/claims.html", context)


def _render_form(request, form, title, subtitle, submit_label, back_url):
    context = _global_context()
    context.update(
        {
            "form": form,
            "title": title,
            "subtitle": subtitle,
            "submit_label": submit_label,
            "back_url": back_url,
            "active_tab": "dashboard",
        }
    )
    return render(
        request,
        "dashboard/form_page.html",
        context,
    )


@login_required
@transaction.atomic
def create_mutuelle(request):
    """Workflow d'onboarding mutuelle (authentifié).

    Étapes prises en charge :
    1. Validation des champs métier (organisation, dimensionnement, objectif immobilier)
    2. Création de la mutuelle (statut ACTIVE) avec slug unique
    3. Provisioning du quota tenant
    4. Rattachement automatique du créateur comme admin mutuelle
    5. Définition de la mutuelle par défaut si l'utilisateur n'en a pas
    """
    form = MutuelleCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        mutuelle = form.save()
        TenantQuota.objects.get_or_create(mutuelle=mutuelle)
        MutuelleMembership.objects.get_or_create(
            mutuelle=mutuelle,
            user=request.user,
            defaults={"role": "admin", "permissions": ["*"], "active": True},
        )
        if not request.user.default_mutuelle_id:
            request.user.default_mutuelle = mutuelle
            request.user.save(update_fields=["default_mutuelle"])
        return redirect("mutuelle-detail", mutuelle_id=mutuelle.id)

    context = _global_context()
    context.update(
        {
            "form": form,
            "title": "Créer une mutuelle",
            "subtitle": "Identifiez l'organisation porteuse, dimensionnez la mutuelle, déclarez l'objectif immobilier et le contact référent.",
            "submit_label": "Créer la mutuelle",
            "back_url": "mutuelles-list",
            "active_tab": "dashboard",
        }
    )
    return render(request, "dashboard/form_mutuelle.html", context)


@login_required
def update_mutuelle_branding(request, mutuelle_id):
    mutuelle = get_object_or_404(Mutuelle, id=mutuelle_id)
    form = MutuelleBrandingForm(request.POST or None, request.FILES or None, instance=mutuelle)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("branding-center")
    return _render_form(request, form, "Personnaliser le branding", "Ajustez l'identité visuelle appliquée à l'espace de la mutuelle.", "Enregistrer", "branding-center")


@login_required
def member_detail(request, member_id):
    """Fiche complète d'un membre.

    Affiche : identité, contact, famille, profession, banque, objectifs
    immobiliers, profil financier, dernière simulation quotité,
    cotisations, paiements, réservations, dettes déclarées.
    """
    member = get_object_or_404(
        Member.all_objects.select_related("mutuelle", "bank"),
        id=member_id,
    )
    mutuelle = member.mutuelle

    # Profil financier (peut ne pas exister)
    fin_profile = getattr(member, "financial_profile", None)

    # Dernière simulation de quotité
    last_simulation = (
        QuotiteCessibleSimulation.all_objects.filter(mutuelle=mutuelle, member=member)
        .order_by("-created_at")
        .first()
    )

    # Activité récente
    contributions = (
        Contribution.all_objects.filter(mutuelle=mutuelle, member=member)
        .select_related("plan")
        .order_by("-created_at")[:10]
    )
    payments = (
        Payment.all_objects.filter(mutuelle=mutuelle, member=member)
        .order_by("-created_at")[:10]
    )
    reservations = (
        PropertyReservation.all_objects.filter(mutuelle=mutuelle, member=member)
        .select_related("lot", "lot__opportunity")
        .order_by("-created_at")[:10]
    )
    claims = (
        AssistanceClaim.all_objects.filter(mutuelle=mutuelle, member=member)
        .order_by("-created_at")[:10]
    )

    # Engagements / dettes déclarés
    from real_estate.models import DebtCommitment

    debts = (
        DebtCommitment.all_objects.filter(mutuelle=mutuelle, member=member)
        .order_by("-created_at")
    )

    # KPI rapides du membre
    paid_total = sum((c.amount for c in contributions if c.status == Contribution.Status.PAID), 0)

    context = _global_context()
    context.update(
        {
            "member": member,
            "mutuelle": mutuelle,
            "active_mutuelle": mutuelle,
            "fin_profile": fin_profile,
            "last_simulation": last_simulation,
            "contributions": contributions,
            "payments": payments,
            "reservations": reservations,
            "claims": claims,
            "debts": debts,
            "paid_total": paid_total,
            "active_tab": "members",
        }
    )
    return render(request, "dashboard/member_detail.html", context)


@login_required
@transaction.atomic
def create_member(request):
    """Workflow d'enrôlement membre complet.

    La mutuelle d'affectation est résolue automatiquement via ``_active_mutuelle``
    (header X-Mutuelle-ID → user.default_mutuelle → MutuelleMembership →
    fallback superuser → premier ACTIVE). L'utilisateur ne la sélectionne
    jamais : on garantit ainsi l'isolation tenant.

    Si vraiment aucune mutuelle n'existe et que l'utilisateur n'est rattaché
    à aucune, on redirige vers la création de mutuelle.
    """
    active_mutuelle = _active_mutuelle(request)
    if not active_mutuelle:
        return redirect("create-mutuelle")

    form = MemberCreateForm(
        request.POST or None,
        request.FILES or None,
        mutuelle=active_mutuelle,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("create-financial-profile")

    context = _global_context()
    context.update(
        {
            "form": form,
            "active_mutuelle": active_mutuelle,
            "title": "Ajouter un membre",
            "subtitle": "Enrôlez un mutualiste : identité, famille, profession, banque affiliée. Le profil financier (revenus, charges, dettes) sera saisi à l'étape suivante.",
            "submit_label": "Enregistrer le membre",
            "back_url": "members-center",
            "active_tab": "members",
        }
    )
    return render(request, "dashboard/form_member.html", context)


@login_required
def create_financial_profile(request):
    """Création du profil financier d'un membre.

    Le membre cible est résolu via :
    1. `?member_id=` (GET) ou `member_id` POST hidden
    2. Sinon : premier membre de la mutuelle active SANS profil financier
       (workflow post-création membre)

    Si aucun candidat trouvé, redirige vers la liste des membres.
    """
    active_mutuelle = _active_mutuelle(request)
    if not active_mutuelle:
        return redirect("create-mutuelle")

    member_id = request.POST.get("member_id") or request.GET.get("member_id")
    member = None
    if member_id:
        member = (
            Member.all_objects.filter(id=member_id, mutuelle=active_mutuelle)
            .select_related("mutuelle")
            .first()
        )
    if member is None:
        member = (
            Member.all_objects.filter(
                mutuelle=active_mutuelle, financial_profile__isnull=True
            )
            .select_related("mutuelle")
            .order_by("-created_at")
            .first()
        )
    if member is None:
        return redirect("members-center")

    # Évite la duplication : si le membre a déjà un profil, on redirige
    if hasattr(member, "financial_profile") and member.financial_profile is not None:
        return redirect("simulations-center")

    form = FinancialProfileForm(request.POST or None, member=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("simulations-center")

    context = _global_context()
    context.update(
        {
            "form": form,
            "target_member": member,
            "active_mutuelle": active_mutuelle,
            "title": f"Profil financier — {member.last_name} {member.first_name}",
            "subtitle": "Revenus, charges, dettes et situation professionnelle. Ces données alimentent la quotité cessible et le scoring.",
            "submit_label": "Enregistrer le profil",
            "back_url": "members-center",
            "active_tab": "members",
        }
    )
    return render(request, "dashboard/form_financial_profile.html", context)


@transaction.atomic
@login_required
def create_project(request):
    form = ProjectCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        mutuelle = data["mutuelle"]
        program = RealEstateProgram.all_objects.create(
            mutuelle=mutuelle,
            name=data["program_name"],
            city=data["city"],
            country=mutuelle.country,
            total_lots=data["total_lots"],
            status=RealEstateProgram.Status.ACTIVE,
            documents_checklist={"titre_foncier": False, "permis_construire": False, "contrat_promoteur": False},
        )
        opportunity = RealEstateOpportunity.all_objects.create(
            mutuelle=mutuelle,
            program=program,
            title=data["opportunity_title"],
            property_type=data["property_type"],
            amount=data["amount"],
            currency=mutuelle.currency,
            initial_deposit=data["initial_deposit"],
            financing_months=data["financing_months"],
            available_lots=data["lots_to_create"],
            status=RealEstateOpportunity.Status.AVAILABLE,
        )
        for index in range(1, data["lots_to_create"] + 1):
            PropertyLot.all_objects.create(
                mutuelle=mutuelle,
                opportunity=opportunity,
                lot_number=f"{data['city'][:3].upper()}-{index:03d}",
                amount=data["amount"],
                currency=mutuelle.currency,
                status=PropertyLot.Status.AVAILABLE,
            )
        compute_program_score(mutuelle, program)
        return redirect("projects-center")
    return _render_form(request, form, "Créer un projet immobilier", "Programme, opportunité, financement et lots générés automatiquement.", "Créer le projet", "projects-center")


@login_required
def create_simulation(request):
    """Lance une simulation de quotité cessible pour un membre donné.

    Résolution du membre cible :
    1. `?member_id=` (GET) ou `member_id` (POST hidden)
    2. À défaut : premier membre de la mutuelle active

    Garde-fous :
    - Aucune mutuelle active → ``create-mutuelle``
    - Aucun membre dans la mutuelle → ``members-center``
    - Membre sans profil financier → ``create-financial-profile?member_id=…``
      avec un message ``warning`` (la simulation a besoin des revenus/charges).
    """
    active_mutuelle = _active_mutuelle(request)
    if not active_mutuelle:
        return redirect("create-mutuelle")

    member_id = request.POST.get("member_id") or request.GET.get("member_id")
    member = None
    if member_id:
        member = (
            Member.all_objects.filter(id=member_id, mutuelle=active_mutuelle)
            .select_related("mutuelle")
            .first()
        )
    if member is None:
        member = (
            Member.all_objects.filter(mutuelle=active_mutuelle)
            .select_related("mutuelle")
            .order_by("-created_at")
            .first()
        )
    if member is None:
        return redirect("members-center")

    # Garde-fou : impossible de simuler sans profil financier (revenus / charges).
    # Le service simulate_quotite() y accède directement → on bloque proprement
    # avec un message explicite + redirection vers la création du profil.
    if not MemberFinancialProfile.all_objects.filter(member=member).exists():
        messages.warning(
            request,
            f"Le profil financier de {member.last_name.upper()} {member.first_name} "
            "n'est pas encore renseigné. Saisissez d'abord les revenus, charges et "
            "engagements pour pouvoir lancer la simulation de quotité cessible.",
        )
        return redirect(
            f"{reverse('create-financial-profile')}?member_id={member.id}"
        )

    form = SimulationCreateForm(request.POST or None, member=member)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        simulate_quotite(
            member.mutuelle,
            member,
            data["requested_amount"],
            data["requested_duration_months"],
            data["annual_interest_rate"],
            data["max_debt_ratio"],
        )
        return redirect("member-detail", member_id=member.id)

    context = _global_context()
    context.update(
        {
            "form": form,
            "target_member": member,
            "active_mutuelle": active_mutuelle,
            "title": f"Lancer une simulation — {member.last_name.upper()} {member.first_name}",
            "subtitle": "Calculez quotité cessible, mensualité, reste à vivre et décision pour ce membre.",
            "submit_label": "Lancer la simulation",
            "back_url": "member-detail",
            "back_kwargs": {"member_id": member.id},
            "active_tab": "members",
        }
    )
    return render(request, "dashboard/form_simulation.html", context)


@login_required
def create_financing_scenario_view(request):
    form = FinancingScenarioCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        create_financing_scenario(
            data["member"].mutuelle,
            data["member"],
            data["opportunity"],
            data["mode"],
            data["personal_deposit"],
            data["duration_months"],
            data["annual_interest_rate"],
        )
        return redirect("financing-center")
    return _render_form(request, form, "Créer un scénario de financement", "Comparez banque, mutuelle, mixte ou épargne progressive.", "Créer le scénario", "financing-center")


@login_required
def create_mortgage_application(request):
    from dashboard.forms import MortgageApplicationCreateForm

    form = MortgageApplicationCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.mutuelle = application.scenario.mutuelle
        application.member = application.scenario.member
        application.save()
        return redirect("financing-center")
    return _render_form(request, form, "Ouvrir un dossier de financement", "Transformez un scénario validé en dossier comité ou banque.", "Ouvrir le dossier", "financing-center")


@login_required
def advance_mortgage_application(request, application_id):
    application = get_object_or_404(MortgageApplication.all_objects, id=application_id)
    transitions = {
        MortgageApplication.Status.DRAFT: MortgageApplication.Status.COMMITTEE,
        MortgageApplication.Status.COMMITTEE: MortgageApplication.Status.BANK_REVIEW,
        MortgageApplication.Status.BANK_REVIEW: MortgageApplication.Status.APPROVED,
        MortgageApplication.Status.APPROVED: MortgageApplication.Status.DISBURSED,
        MortgageApplication.Status.DISBURSED: MortgageApplication.Status.CLOSED,
    }
    if request.method == "POST" and application.status in transitions:
        application.status = transitions[application.status]
        if application.status == MortgageApplication.Status.DISBURSED and not application.disbursed_amount:
            application.disbursed_amount = application.scenario.principal
        application.save(update_fields=["status", "disbursed_amount", "updated_at"])
    return redirect("financing-center")


@login_required
def create_reservation(request):
    form = ReservationCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reservation = form.save(commit=False)
        reservation.mutuelle = reservation.member.mutuelle
        reservation.status = PropertyReservation.Status.PENDING
        reservation.save()
        reservation.lot.status = PropertyLot.Status.RESERVED
        reservation.lot.assigned_member = reservation.member
        reservation.lot.save(update_fields=["status", "assigned_member"])
        return redirect("projects-center")
    return _render_form(request, form, "Réserver un lot", "Affectez un lot à un membre et tracez l'acompte.", "Réserver le lot", "projects-center")


@login_required
def create_contribution_plan(request):
    form = ContributionPlanCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("finance-center")
    return _render_form(request, form, "Créer un plan de cotisation", "Définissez le montant, la fréquence et les pénalités.", "Créer le plan", "finance-center")


@login_required
def create_contribution(request):
    form = ContributionCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contribution = form.save(commit=False)
        contribution.mutuelle = contribution.member.mutuelle
        if not contribution.currency:
            contribution.currency = contribution.mutuelle.currency
        if contribution.status == Contribution.Status.PAID:
            contribution.paid_at = timezone.now()
            contribution.receipt_number = f"RCT-{uuid.uuid4().hex[:10].upper()}"
        contribution.save()
        return redirect("finance-center")
    return _render_form(request, form, "Créer une cotisation", "Générez une échéance pour un membre.", "Créer la cotisation", "finance-center")


@login_required
def create_payment(request):
    form = PaymentCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if data["provider"] in {Payment.Provider.ORANGE, Payment.Provider.MTN, Payment.Provider.WAVE, Payment.Provider.MOOV}:
            initiate_mobile_money_payment(
                data["member"].mutuelle,
                {
                    "provider": data["provider"],
                    "member": data["member"],
                    "phone": data["phone"],
                    "amount": data["amount"],
                    "currency": data["currency"],
                    "purpose": data["purpose"],
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
        else:
            payment = form.save(commit=False)
            payment.mutuelle = payment.member.mutuelle
            payment.status = Payment.Status.PENDING
            payment.idempotency_key = uuid.uuid4().hex
            payment.provider_payload = {"source": "console", "intent": "collect"}
            payment.save()
        return redirect("finance-center")
    return _render_form(request, form, "Initier un paiement", "Préparez une collecte Mobile Money ou caisse.", "Initier le paiement", "finance-center")


@login_required
def simulate_payment_success(request, payment_id):
    payment = get_object_or_404(Payment.all_objects, id=payment_id)
    if request.method == "POST":
        process_mobile_money_webhook({"reference": payment.external_reference, "status": "success", "source": "console_simulation"})
    return redirect("finance-center")


@login_required
def create_assistance_claim(request):
    form = AssistanceClaimCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        claim = form.save(commit=False)
        claim.mutuelle = claim.member.mutuelle
        if not claim.currency:
            claim.currency = claim.mutuelle.currency
        claim.save()
        return redirect("claims-center")
    return _render_form(request, form, "Créer une demande d'assistance", "Maladie, décès, accident, maternité ou aide sociale avec workflow de décision.", "Créer la demande", "claims-center")


@login_required
def advance_assistance_claim(request, claim_id):
    claim = get_object_or_404(AssistanceClaim.all_objects, id=claim_id)
    if request.method == "POST":
        advance_claim(claim)
    return redirect("claims-center")


@login_required
def upload_property_document(request):
    form = PropertyDocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.mutuelle = document.program.mutuelle
        document.ocr_payload = {
            "status": "queued",
            "engine": "hybrid_ocr",
            "message": "Analyse OCR prête pour traitement asynchrone.",
        }
        document.save()
        return redirect("documents-center")
    return _render_form(request, form, "Importer un document", "Ajoutez un titre foncier, permis, contrat promoteur ou document KYC.", "Importer le document", "documents-center")


@login_required
def process_property_document(request, document_id):
    document = get_object_or_404(PropertyDocument.all_objects, id=document_id)
    if request.method == "POST":
        process_property_document_ocr(str(document.id))
    return redirect("documents-center")


@login_required
def create_notification(request):
    form = NotificationCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        queue_notification(
            mutuelle=data["mutuelle"],
            title=data["title"],
            body=data["body"],
            channel=data["channel"],
            member=data.get("member"),
            metadata={"source": "console", "priority": "normal"},
        )
        return redirect("notifications-center")
    return _render_form(request, form, "Créer une notification", "Préparez un message SMS, WhatsApp, email, push ou temps réel.", "Créer la notification", "notifications-center")


@login_required
def create_ai_decision_note(request):
    form = AIAnalysisCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        mutuelle = form.cleaned_data["mutuelle"]
        result = generate_mutuelle_decision_note(mutuelle)
        AIAnalysis.all_objects.create(
            mutuelle=mutuelle,
            analysis_type="mutuelle_decision_note",
            provider=form.cleaned_data["provider"],
            prompt=form.cleaned_data["prompt"],
            result=result,
            confidence=82,
            related_object_type="Mutuelle",
            related_object_id=str(mutuelle.id),
        )
        return redirect("ai-copilot-center")
    return _render_form(request, form, "Générer une note IA", "Analyse comité, capacité collective, risques de programme et recommandations banque.", "Générer la note", "ai-copilot-center")


@login_required
def request_mfa_challenge(request):
    form = MFARequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        challenge, code = create_otp_challenge(form.cleaned_data["user"], channel=form.cleaned_data["channel"])
        challenge.delivery_target = f"{challenge.delivery_target} · DEV {code}"
        challenge.save(update_fields=["delivery_target"])
        return redirect("security-center")
    return _render_form(request, form, "Générer un OTP", "Créez un code temporaire pour activer ou vérifier MFA.", "Générer", "security-center")


@login_required
def verify_mfa_challenge(request):
    form = MFAVerifyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        challenge = form.cleaned_data["challenge"]
        if verify_otp_challenge(challenge, form.cleaned_data["code"]):
            challenge.user.mfa_enabled = True
            challenge.user.save(update_fields=["mfa_enabled"])
        return redirect("security-center")
    return _render_form(request, form, "Vérifier un OTP", "Validez le code reçu et activez MFA pour l'utilisateur.", "Vérifier", "security-center")


@login_required
def create_assembly(request):
    form = GeneralAssemblyCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("governance-center")
    return _render_form(request, form, "Planifier une AG", "Convocation, quorum, lieu ou lien visio pour la mutuelle.", "Créer l'assemblée", "governance-center")


@login_required
def create_resolution(request):
    form = ResolutionCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        resolution = form.save(commit=False)
        resolution.mutuelle = resolution.assembly.mutuelle
        resolution.save()
        return redirect("governance-center")
    return _render_form(request, form, "Créer une résolution", "Préparez un vote électronique traçable pour l'assemblée générale.", "Créer la résolution", "governance-center")


@login_required
def mutuelle_report(request, mutuelle_id):
    mutuelle = get_object_or_404(Mutuelle, id=mutuelle_id)
    context = _mutuelle_context(mutuelle)
    context["members"] = Member.all_objects.filter(mutuelle=mutuelle).order_by("last_name")[:12]
    context["documents"] = PropertyDocument.all_objects.filter(mutuelle=mutuelle).select_related("program").order_by("-created_at")[:12]
    context["contributions"] = Contribution.all_objects.filter(mutuelle=mutuelle).select_related("member", "plan").order_by("-created_at")[:12]
    context["generated_at"] = timezone.now()
    return render(request, "dashboard/mutuelle_report.html", context)


@login_required
def mutuelle_report_pdf(request, mutuelle_id):
    mutuelle = get_object_or_404(Mutuelle, id=mutuelle_id)
    context = _mutuelle_context(mutuelle)
    pdf = mutuelle_health_report_pdf(mutuelle, context)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="rapport-{mutuelle.slug}.pdf"'
    return response


@login_required
def contribution_receipt(request, contribution_id):
    contribution = get_object_or_404(
        Contribution.all_objects.select_related("mutuelle", "member", "plan"),
        id=contribution_id,
    )
    if not contribution.receipt_number:
        contribution.receipt_number = f"RCT-{uuid.uuid4().hex[:10].upper()}"
        contribution.save(update_fields=["receipt_number", "updated_at"])
    pdf = contribution_receipt_pdf(contribution)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="recu-{contribution.receipt_number}.pdf"'
    return response


@login_required
def finance_export_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="finances-dga-imo360.csv"'
    writer = csv.writer(response)
    writer.writerow(["Mutuelle", "Membre", "Plan", "Montant", "Devise", "Echeance", "Statut", "Numero recu"])
    contributions = Contribution.all_objects.select_related("mutuelle", "member", "plan").order_by("-created_at")[:1000]
    for contribution in contributions:
        writer.writerow(
            [
                contribution.mutuelle.name,
                f"{contribution.member.first_name} {contribution.member.last_name}",
                contribution.plan.name if contribution.plan else "",
                contribution.amount,
                contribution.currency,
                contribution.due_date.isoformat(),
                contribution.get_status_display(),
                contribution.receipt_number,
            ]
        )
    return response
