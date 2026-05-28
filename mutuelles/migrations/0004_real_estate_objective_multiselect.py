# Conversion real_estate_objective : CharField → JSONField (multi-select)

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
    """Convertit l'ancienne valeur unique en liste à 1 élément."""
    Mutuelle = apps.get_model("mutuelles", "Mutuelle")
    for mutuelle in Mutuelle.objects.all():
        legacy = (getattr(mutuelle, "_legacy_real_estate_objective", "") or "").strip()
        if legacy in VALID_CHOICES:
            mutuelle.real_estate_objective = [legacy]
        else:
            mutuelle.real_estate_objective = []
        mutuelle.save(update_fields=["real_estate_objective"])


def backward(apps, schema_editor):
    """Reverse : conserve seulement le premier objectif."""
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
        # 1. L'index composite sur l'ancien CharField est retiré (incompatible JSONField)
        migrations.RemoveIndex(
            model_name="mutuelle",
            name="mutuelles_m_re_obj_status_idx",
        ),
        # 2. Renomme l'ancien champ pour libérer le nom
        migrations.RenameField(
            model_name="mutuelle",
            old_name="real_estate_objective",
            new_name="_legacy_real_estate_objective",
        ),
        # 3. Crée le nouveau JSONField sous le nom canonique
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
        # 4. Migre les données (ancien → liste)
        migrations.RunPython(forward, backward),
        # 5. Retire le champ legacy
        migrations.RemoveField(
            model_name="mutuelle",
            name="_legacy_real_estate_objective",
        ),
    ]
