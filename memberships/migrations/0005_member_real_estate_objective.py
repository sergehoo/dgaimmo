# Ajout du champ real_estate_objective sur Member (multi-select)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("memberships", "0004_rename_memberships_bank_country_active_idx_memberships_country_95da46_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="real_estate_objective",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Liste des objectifs immobiliers visés par ce membre (sélection multiple).",
                verbose_name="Objectifs immobiliers du membre",
            ),
        ),
    ]
