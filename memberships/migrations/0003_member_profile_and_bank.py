# Generated for MutuelleX member profile + bank affiliation

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("memberships", "0002_alter_member_location"),
    ]

    operations = [
        # --- Bank model ---
        migrations.CreateModel(
            name="Bank",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(db_index=True, max_length=180, verbose_name="Nom de la banque")),
                ("code", models.CharField(blank=True, db_index=True, max_length=24, verbose_name="Code/abréviation")),
                ("country", models.CharField(db_index=True, default="CI", max_length=2)),
                ("website", models.URLField(blank=True)),
                (
                    "is_partner",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text="Banque partenaire offrant des produits prêt immobilier.",
                        verbose_name="Partenaire programme",
                    ),
                ),
                ("active", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["country", "active"], name="memberships_bank_country_active_idx"),
                ],
            },
        ),
        # --- Member enrichment ---
        migrations.AddField(
            model_name="member",
            name="birth_place",
            field=models.CharField(blank=True, max_length=160, verbose_name="Lieu de naissance"),
        ),
        migrations.AddField(
            model_name="member",
            name="marital_status",
            field=models.CharField(
                choices=[
                    ("single", "Célibataire"),
                    ("married", "Marié(e)"),
                    ("divorced", "Divorcé(e)"),
                    ("widowed", "Veuf / Veuve"),
                    ("union_libre", "Union libre"),
                    ("other", "Autre"),
                ],
                db_index=True,
                default="single",
                max_length=24,
                verbose_name="Situation matrimoniale",
            ),
        ),
        migrations.AddField(
            model_name="member",
            name="dependents_count",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Enfants, conjoint(s), parents à charge...",
                verbose_name="Nombre de personnes à charge",
            ),
        ),
        migrations.AddField(
            model_name="member",
            name="spouse_name",
            field=models.CharField(blank=True, max_length=180, verbose_name="Nom du conjoint"),
        ),
        migrations.AddField(
            model_name="member",
            name="employer",
            field=models.CharField(blank=True, max_length=180, verbose_name="Entreprise / employeur"),
        ),
        migrations.AddField(
            model_name="member",
            name="job_function",
            field=models.CharField(blank=True, max_length=160, verbose_name="Fonction dans l'entreprise"),
        ),
        migrations.AddField(
            model_name="member",
            name="professional_seniority_months",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Ancienneté totale dans le poste / l'entreprise.",
                verbose_name="Ancienneté (mois)",
            ),
        ),
        migrations.AddField(
            model_name="member",
            name="hire_date",
            field=models.DateField(blank=True, null=True, verbose_name="Date d'embauche"),
        ),
        migrations.AddField(
            model_name="member",
            name="bank",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="affiliated_members",
                to="memberships.bank",
                verbose_name="Banque affiliée",
            ),
        ),
        migrations.AddField(
            model_name="member",
            name="bank_account_number",
            field=models.CharField(blank=True, max_length=64, verbose_name="Numéro de compte / IBAN"),
        ),
        migrations.AlterField(
            model_name="member",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "Masculin"), ("female", "Féminin"), ("other", "Autre")],
                max_length=20,
                verbose_name="Genre",
            ),
        ),
        migrations.AlterField(
            model_name="member",
            name="first_name",
            field=models.CharField(max_length=120, verbose_name="Prénom(s)"),
        ),
        migrations.AlterField(
            model_name="member",
            name="last_name",
            field=models.CharField(max_length=120, verbose_name="Nom"),
        ),
        migrations.AlterField(
            model_name="member",
            name="phone",
            field=models.CharField(db_index=True, max_length=32, verbose_name="Téléphone"),
        ),
        migrations.AlterField(
            model_name="member",
            name="email",
            field=models.EmailField(blank=True, db_index=True, max_length=254, verbose_name="Email contact"),
        ),
        migrations.AlterField(
            model_name="member",
            name="birth_date",
            field=models.DateField(blank=True, null=True, verbose_name="Date de naissance"),
        ),
        migrations.AlterField(
            model_name="member",
            name="national_id",
            field=models.CharField(blank=True, db_index=True, max_length=80, verbose_name="CNI / Passeport"),
        ),
        migrations.AddIndex(
            model_name="member",
            index=models.Index(fields=["mutuelle", "marital_status"], name="memberships_m_marital_idx"),
        ),
        migrations.AddIndex(
            model_name="member",
            index=models.Index(fields=["mutuelle", "bank"], name="memberships_m_bank_idx"),
        ),
    ]
