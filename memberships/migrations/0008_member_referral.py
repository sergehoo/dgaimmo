"""Ajoute le parrainage aux membres.

Compatible SQLite (dev/tests) et PostgreSQL (prod). Pour Postgres, on
utilise du SQL idempotent (DO $$ … END $$) qui vérifie l'existence des
colonnes avant l'ALTER TABLE — utile si la base a déjà été partiellement
migrée manuellement. Sur SQLite, on laisse Django créer les colonnes via
les opérations standard AddField.
"""

from django.db import migrations, models


PG_ADD_REFERRAL_CODE = """
DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'memberships_member' AND column_name = 'referral_code'
  ) THEN
      ALTER TABLE memberships_member
          ADD COLUMN referral_code varchar(24) NULL;
      CREATE UNIQUE INDEX memberships_member_referral_code_key
          ON memberships_member (referral_code);
  END IF;
END $$;
"""

PG_ADD_REFERRED_BY = """
DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'memberships_member' AND column_name = 'referred_by_id'
  ) THEN
      ALTER TABLE memberships_member
          ADD COLUMN referred_by_id bigint NULL;
      ALTER TABLE memberships_member
          ADD CONSTRAINT memberships_member_referred_by_fk
          FOREIGN KEY (referred_by_id) REFERENCES memberships_member(id)
          ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
      CREATE INDEX memberships_member_referred_by_idx
          ON memberships_member (referred_by_id);
  END IF;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("memberships", "0007_bank_mortgage_fields_and_seed"),
    ]

    operations = [
        # Chemin standard Django (SQLite, MySQL, et pour l'état Postgres).
        migrations.AddField(
            model_name="member",
            name="referral_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Code unique généré à l'adhésion, partageable pour parrainer d'autres membres.",
                max_length=24,
                null=True,
                unique=True,
                verbose_name="Code de parrainage",
            ),
        ),
        migrations.AddField(
            model_name="member",
            name="referred_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Membre qui a parrainé ce mutualiste (via un lien de parrainage).",
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="referrals",
                to="memberships.member",
                verbose_name="Parrain",
            ),
        ),
    ]
