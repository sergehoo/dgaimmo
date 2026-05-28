# Generated for MutuelleX onboarding update

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mutuelles", "0002_alter_mutuelle_headquarters_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="mutuelle",
            name="organization_name",
            field=models.CharField(
                blank=True,
                help_text="Entité juridique, association, communauté ou groupe à l'origine de la mutuelle.",
                max_length=180,
                verbose_name="Entreprise / organisation",
            ),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="organization_type",
            field=models.CharField(
                choices=[
                    ("entreprise", "Entreprise"),
                    ("association", "Association"),
                    ("cooperative", "Coopérative"),
                    ("communaute", "Communauté"),
                    ("administration", "Administration"),
                    ("groupe_informel", "Groupe informel"),
                    ("autre", "Autre"),
                ],
                db_index=True,
                default="autre",
                max_length=32,
                verbose_name="Type d'organisation",
            ),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="estimated_members_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Estimation initiale pour dimensionner la mutuelle et le scoring.",
                validators=[MinValueValidator(0)],
                verbose_name="Nombre estimé de membres",
            ),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="real_estate_objective",
            field=models.CharField(
                choices=[
                    ("terrain", "Terrain"),
                    ("maison", "Maison / villa"),
                    ("immeuble", "Immeuble"),
                    ("appartement", "Appartement"),
                    ("logement_social", "Logement social"),
                    ("programme_promoteur", "Programme promoteur"),
                    ("construction_collective", "Construction collective"),
                    ("autre", "Autre objectif"),
                ],
                db_index=True,
                default="autre",
                max_length=40,
                verbose_name="Objectif immobilier",
            ),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="real_estate_objective_details",
            field=models.TextField(
                blank=True,
                help_text="Décrivez librement le projet (zone, budget cible, calendrier...).",
                verbose_name="Précisions sur l'objectif immobilier",
            ),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="contact_last_name",
            field=models.CharField(blank=True, max_length=120, verbose_name="NOM du contact"),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="contact_first_name",
            field=models.CharField(blank=True, max_length=120, verbose_name="Prénom(s) du contact"),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="contact_function",
            field=models.CharField(
                blank=True,
                help_text="Fonction au sein de l'organisation (Président, DG, RH, Trésorier...).",
                max_length=120,
                verbose_name="Fonction du contact",
            ),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="contact_email",
            field=models.EmailField(blank=True, db_index=True, max_length=254, verbose_name="Email du contact"),
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="contact_phone",
            field=models.CharField(blank=True, max_length=32, verbose_name="Téléphone du contact"),
        ),
        migrations.AddIndex(
            model_name="mutuelle",
            index=models.Index(fields=["real_estate_objective", "status"], name="mutuelles_m_re_obj_status_idx"),
        ),
        migrations.AddIndex(
            model_name="mutuelle",
            index=models.Index(fields=["organization_type", "status"], name="mutuelles_m_org_status_idx"),
        ),
    ]
