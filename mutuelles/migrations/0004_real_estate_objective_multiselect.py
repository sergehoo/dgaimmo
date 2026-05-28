# Conversion real_estate_objective : CharField → JSONField (multi-select)
# + Réalignement des hashes d'index (Django 6.0+) et propagation des verbose_name.

from django.db import migrations, models


VALID_CHOICES = {
    "terrain",
    "maison",
    "immeuble",
    "appartement",
    "logement_social",
    "programme_promoteur",
    "construction_collective",
    "autre",
}


def forward(apps, schema_editor):
    """Convertit l'ancienne valeur unique (CharField) en liste à 1 élément."""
    Mutuelle = apps.get_model("mutuelles", "Mutuelle")
    for mutuelle in Mutuelle.objects.all():
        legacy = (getattr(mutuelle, "_legacy_real_estate_objective", "") or "").strip()
        if legacy in VALID_CHOICES:
            mutuelle.real_estate_objective = [legacy]
        else:
            mutuelle.real_estate_objective = []
        mutuelle.save(update_fields=["real_estate_objective"])


def backward(apps, schema_editor):
    """Reverse : conserve le premier objectif."""
    Mutuelle = apps.get_model("mutuelles", "Mutuelle")
    for mutuelle in Mutuelle.objects.all():
        values = mutuelle.real_estate_objective or []
        first = values[0] if values and values[0] in VALID_CHOICES else "autre"
        mutuelle._legacy_real_estate_objective = first
        mutuelle.save(update_fields=["_legacy_real_estate_objective"])


class Migration(migrations.Migration):

    dependencies = [
        ("mutuelles", "0003_mutuelle_onboarding_fields"),
    ]

    operations = [
        # ---------------------------------------------------------------
        # 1. Réalignement des noms d'index (Django 6.0 utilise un hash
        #    différent de celui qu'on avait écrit en dur dans 0003).
        # ---------------------------------------------------------------
        migrations.RenameIndex(
            model_name="mutuelle",
            old_name="mutuelles_m_org_status_idx",
            new_name="mutuelles_m_organiz_eb557f_idx",
        ),
        # ---------------------------------------------------------------
        # 2. Propagation des verbose_name FR sur les CharField identité.
        #    (modifs apportées au modèle Mutuelle dans 0003 mais Django 6
        #     les redétecte au makemigrations).
        # ---------------------------------------------------------------
        migrations.AlterField(
            model_name="mutuelle",
            name="name",
            field=models.CharField(db_index=True, max_length=180, verbose_name="Nom de la mutuelle"),
        ),
        migrations.AlterField(
            model_name="mutuelle",
            name="legal_name",
            field=models.CharField(blank=True, max_length=180, verbose_name="Raison sociale"),
        ),
        # ---------------------------------------------------------------
        # 3. Retire l'index composite sur l'ancien CharField (incompatible
        #    avec un JSONField — les filtres par contenu se font via JSONB).
        # ---------------------------------------------------------------
        migrations.RemoveIndex(
            model_name="mutuelle",
            name="mutuelles_m_re_obj_status_idx",
        ),
        # ---------------------------------------------------------------
        # 4. Bascule du champ CharField → JSONField avec migration de données.
        # ---------------------------------------------------------------
        migrations.RenameField(
            model_name="mutuelle",
            old_name="real_estate_objective",
            new_name="_legacy_real_estate_objective",
        ),
        migrations.AddField(
            model_name="mutuelle",
            name="real_estate_objective",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Liste des objectifs immobiliers visés (sélection multiple).",
                verbose_name="Objectifs immobiliers",
            ),
        ),
        migrations.RunPython(forward, backward),
        migrations.RemoveField(
            model_name="mutuelle",
            name="_legacy_real_estate_objective",
        ),
    ]
