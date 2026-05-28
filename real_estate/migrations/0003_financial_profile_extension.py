# Generated for MutuelleX MemberFinancialProfile extension

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("real_estate", "0002_alter_realestateprogram_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="memberfinancialprofile",
            name="existing_loan_payments",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Somme des mensualités de tous les prêts bancaires/microcrédits en cours.",
                max_digits=14,
                verbose_name="Prêts en cours (mensualité totale)",
            ),
        ),
        migrations.AddField(
            model_name="memberfinancialprofile",
            name="other_debts",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Dettes hors prêts (loyer impayé, dettes familiales, etc.).",
                max_digits=14,
                verbose_name="Autres dettes mensualisées",
            ),
        ),
        migrations.AddField(
            model_name="memberfinancialprofile",
            name="pensions_paid",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=14,
                verbose_name="Pensions versées (alimentaire...)",
            ),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="net_monthly_salary",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Revenu mensuel net"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="complementary_income",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Revenus complémentaires"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="pensions",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Pensions reçues"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="fixed_charges",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Charges mensuelles fixes"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="mutual_contributions",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Cotisations mutuelle"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="dependents_count",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="Personnes à charge"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="professional_seniority_months",
            field=models.PositiveIntegerField(default=0, verbose_name="Ancienneté professionnelle (mois)"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="contract_type",
            field=models.CharField(blank=True, max_length=80, verbose_name="Type de contrat (CDI, CDD...)"),
        ),
        migrations.AlterField(
            model_name="memberfinancialprofile",
            name="employment_type",
            field=models.CharField(
                choices=[
                    ("public", "Fonctionnaire"),
                    ("private", "Salarié privé"),
                    ("independent", "Indépendant"),
                    ("informal", "Revenus informels"),
                    ("retired", "Retraité"),
                    ("student", "Étudiant"),
                ],
                default="private",
                max_length=24,
                verbose_name="Statut professionnel",
            ),
        ),
    ]
