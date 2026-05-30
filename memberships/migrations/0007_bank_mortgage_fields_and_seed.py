# Bank : ajout taux/durée/montant min + seed des banques UEMOA majeures

from decimal import Decimal

from django.db import migrations, models


# Catalogue indicatif des principales banques de Côte d'Ivoire / UEMOA
# avec leurs taux annuels TEG approximatifs pour le crédit immobilier.
# Source : moyennes marché 2024-2026 — à actualiser via l'admin si besoin.
LOCAL_BANKS = [
    # (name, code, country, default_rate, max_months, min_amount, is_partner, website)
    ("SGBCI — Société Générale Côte d'Ivoire", "SGCI", "CI", Decimal("7.50"), 300, Decimal("5000000"), True,  "https://societegenerale.ci"),
    ("SIB — Société Ivoirienne de Banque",      "SIB",  "CI", Decimal("8.00"), 240, Decimal("3000000"), True,  "https://www.sib.ci"),
    ("Ecobank Côte d'Ivoire",                   "ECOB", "CI", Decimal("7.00"), 300, Decimal("5000000"), True,  "https://ecobank.com"),
    ("BOA — Bank of Africa Côte d'Ivoire",      "BOA",  "CI", Decimal("8.00"), 240, Decimal("3000000"), True,  "https://boacotedivoire.com"),
    ("NSIA Banque",                              "NSIA", "CI", Decimal("7.50"), 240, Decimal("3000000"), True,  "https://nsiabanque.ci"),
    ("BICICI — BNP Paribas",                     "BICI", "CI", Decimal("8.00"), 240, Decimal("5000000"), True,  "https://www.bicici.com"),
    ("Banque Atlantique Côte d'Ivoire",          "BACI", "CI", Decimal("7.50"), 240, Decimal("3000000"), True,  "https://banqueatlantique.net"),
    ("Orabank Côte d'Ivoire",                    "ORAB", "CI", Decimal("8.50"), 180, Decimal("2000000"), False, "https://orabank.net"),
    ("UBA Côte d'Ivoire",                        "UBA",  "CI", Decimal("8.00"), 240, Decimal("3000000"), True,  "https://www.ubagroup.com"),
    ("Coris Bank International",                 "CBI",  "CI", Decimal("7.50"), 240, Decimal("3000000"), True,  "https://www.corisbank.com"),
    ("BHCI — Banque de l'Habitat de Côte d'Ivoire", "BHCI", "CI", Decimal("6.50"), 360, Decimal("2000000"), True,  "https://www.bhci.ci"),
    ("BNI — Banque Nationale d'Investissement",  "BNI",  "CI", Decimal("7.00"), 300, Decimal("5000000"), True,  ""),
]


def seed_banks(apps, schema_editor):
    Bank = apps.get_model("memberships", "Bank")
    for name, code, country, rate, months, minamt, is_partner, website in LOCAL_BANKS:
        Bank.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "country": country,
                "website": website,
                "is_partner": is_partner,
                "active": True,
                "default_mortgage_rate": rate,
                "mortgage_max_duration_months": months,
                "mortgage_min_amount": minamt,
            },
        )


def unseed_banks(apps, schema_editor):
    Bank = apps.get_model("memberships", "Bank")
    Bank.objects.filter(code__in=[code for _, code, *_ in LOCAL_BANKS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("memberships", "0006_member_invitation"),
    ]

    operations = [
        migrations.AddField(
            model_name="bank",
            name="default_mortgage_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Taux annuel TEG indicatif pour le crédit immobilier (peut varier selon profil).",
                max_digits=5,
                verbose_name="Taux annuel indicatif (%)",
            ),
        ),
        migrations.AddField(
            model_name="bank",
            name="mortgage_max_duration_months",
            field=models.PositiveIntegerField(
                default=240,
                help_text="Durée maximale du prêt immobilier (240 mois = 20 ans par défaut).",
                verbose_name="Durée max prêt immobilier (mois)",
            ),
        ),
        migrations.AddField(
            model_name="bank",
            name="mortgage_min_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Montant minimum d'octroi pour un prêt immobilier.",
                max_digits=14,
                verbose_name="Montant minimum (FCFA)",
            ),
        ),
        migrations.RunPython(seed_banks, unseed_banks),
    ]
