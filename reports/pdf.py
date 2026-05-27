from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value, currency="FCFA"):
    return f"{value:,.0f} {currency}".replace(",", " ")


def _build_pdf(title, subtitle, story):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    content = [
        Paragraph("DGA-IMO360", styles["Title"]),
        Paragraph(title, styles["Heading1"]),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]
    content.extend(story)
    document.build(content)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def contribution_receipt_pdf(contribution):
    styles = getSampleStyleSheet()
    rows = [
        ["Reçu", contribution.receipt_number or "En attente"],
        ["Mutuelle", contribution.mutuelle.name],
        ["Membre", f"{contribution.member.first_name} {contribution.member.last_name}"],
        ["Plan", contribution.plan.name if contribution.plan else "-"],
        ["Montant", _money(contribution.amount, contribution.currency)],
        ["Pénalité", _money(contribution.penalty_amount, contribution.currency)],
        ["Échéance", contribution.due_date.strftime("%d/%m/%Y")],
        ["Statut", contribution.get_status_display()],
    ]
    if contribution.paid_at:
        rows.append(["Payé le", contribution.paid_at.strftime("%d/%m/%Y %H:%M")])
    table = Table(rows, colWidths=[5 * cm, 11 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef4ff")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#06194a")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe6f5")),
                ("PADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story = [
        Paragraph("Ce reçu confirme l'enregistrement de la cotisation dans la caisse mutualiste.", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        table,
        Spacer(1, 0.6 * cm),
        Paragraph("Document généré automatiquement. Vérifiez le numéro de reçu et le statut avant archivage.", styles["Italic"]),
    ]
    return _build_pdf("Reçu de cotisation", f"{contribution.mutuelle.name} · {contribution.currency}", story)


def mutuelle_health_report_pdf(mutuelle, context):
    styles = getSampleStyleSheet()
    score = context.get("score")
    rows = [
        ["Membres actifs", str(context.get("active_members", 0))],
        ["Trésorerie", _money(context.get("treasury_balance", 0), mutuelle.currency)],
        ["Capacité collective", _money(context.get("collective_capacity", 0), mutuelle.currency)],
        ["Programmes", str(context.get("programs_count", 0))],
        ["Réservations", str(context.get("reservations_count", 0))],
        ["Score global", f"{score.score if score else 0}/100"],
        ["Niveau santé", score.health_level if score else "Analyse en cours"],
        ["Risque", score.risk_level if score else "-"],
    ]
    table = Table(rows, colWidths=[6 * cm, 10 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef4ff")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe6f5")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    recommendations = []
    if score:
        recommendations = [Paragraph(f"- {item}", styles["Normal"]) for item in score.recommendations]
    story = [
        Paragraph("Rapport synthétique de solvabilité collective, destiné au comité de mutuelle et aux partenaires bancaires.", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        table,
        Spacer(1, 0.6 * cm),
        Paragraph("Recommandations", styles["Heading2"]),
        *(recommendations or [Paragraph("- Compléter les données financières et documentaires.", styles["Normal"])]),
    ]
    return _build_pdf("Rapport de santé financière", f"{mutuelle.legal_name} · {mutuelle.country}", story)
