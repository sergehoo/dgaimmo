# Conversion real_estate_objective : CharField → JSONField (multi-select)
# + Réalignement des hashes d'index (Django 6.0+) et propagation des verbose_name.
#
# IDEMPOTENT : utilise du SQL conditionnel pour gérer le cas où une
# auto-migration intermédiaire aurait déjà renommé/supprimé certains index.

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


# --- SQL idempotent pour les renames/drops d'index ------------------------
# On utilise IF EXISTS / pg_indexes pour ne pas crasher si une migration
# intermédiaire (ou un --fake antérieur) a déjà fait le travail.

RENAME_ORG_INDEX_SQL = """
DO $$
DECLARE
    has_legacy boolean;
    has_target boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'mutuelles_mutuelle'
          AND indexname = 'mutuelles_m_org_status_idx'
    ) INTO has_legacy;
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'mutuelles_mutuelle'
          AND indexname = 'mutuelles_m_organiz_eb557f_idx'
    ) INTO has_target;

    IF has_legacy AND NOT has_target THEN
        EXECUTE 'ALTER INDEX mutuelles_m_org_status_idx RENAME TO mutuelles_m_organiz_eb557f_idx';
    ELSIF has_legacy AND has_target THEN
        -- target déjà créé par une autre migration → on supprime juste le legacy
        EXECUTE 'DROP INDEX mutuelles_m_org_status_idx';
    END IF;
END
$$;
"""

REVERSE_RENAME_ORG_INDEX_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'mutuelles_mutuelle'
          AND indexname = 'mutuelles_m_organiz_eb557f_idx'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'mutuelles_mutuelle'
          AND indexname = 'mutuelles_m_org_status_idx'
    ) THEN
        EXECUTE 'ALTER INDEX mutuelles_m_organiz_eb557f_idx RENAME TO mutuelles_m_org_status_idx';
    END IF;
END
$$;
"""

DROP_REOBJ_INDEX_SQL = """
DO $$
DECLARE
    idx_name text;
BEGIN
    -- Drop l'index qu'il soit nommé mutuelles_m_re_obj_status_idx
    -- ou mutuelles_m_real_es_fa5013_idx (Django 6 auto-hash)
    FOR idx_name IN
        SELECT indexname FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'mutuelles_mutuelle'
          AND indexname IN (
              'mutuelles_m_re_obj_status_idx',
              'mutuelles_m_real_es_fa5013_idx'
          )
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
    END LOOP;
END
$$;
"""

NOOP_SQL = "SELECT 1;"


class Migration(migrations.Migration):

    dependencies = [
        ("mutuelles", "0003_mutuelle_onboarding_fields"),
    ]

    operations = [
        # ---------------------------------------------------------------
        # 1. Réalignement de l'index (organization_type, status) sur le
        #    nom Django 6 — IDEMPOTENT (gère 3 cas : pas d'index, ancien
        #    nom, nouveau nom déjà présent).
        # ---------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=RENAME_ORG_INDEX_SQL,
                    reverse_sql=REVERSE_RENAME_ORG_INDEX_SQL,
                ),
            ],
            state_operations=[
                migrations.RenameIndex(
                    model_name="mutuelle",
                    old_name="mutuelles_m_org_status_idx",
                    new_name="mutuelles_m_organiz_eb557f_idx",
                ),
            ],
        ),
        # ---------------------------------------------------------------
        # 2. Propagation des verbose_name FR sur les CharField identité.
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
        # 3. Retire l'index composite sur l'ancien CharField — IDEMPOTENT
        #    (drop par nom legacy OU par nom auto-hash Django 6).
        # ---------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(sql=DROP_REOBJ_INDEX_SQL, reverse_sql=NOOP_SQL),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="mutuelle",
                    name="mutuelles_m_re_obj_status_idx",
                ),
            ],
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
