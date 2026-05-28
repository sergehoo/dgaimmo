from django.db import migrations

from core.fields import geo_point_field


def recreate_geography_column(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    schema_editor.execute('ALTER TABLE "real_estate_realestateprogram" DROP COLUMN IF EXISTS "location"')
    schema_editor.execute('ALTER TABLE "real_estate_realestateprogram" ADD COLUMN "location" geography(POINT,4326) NULL')


def recreate_json_column(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute('ALTER TABLE "real_estate_realestateprogram" DROP COLUMN IF EXISTS "location"')
    schema_editor.execute('ALTER TABLE "real_estate_realestateprogram" ADD COLUMN "location" jsonb NULL')


class Migration(migrations.Migration):
    dependencies = [
        ("real_estate", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(recreate_geography_column, recreate_json_column),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="realestateprogram",
                    name="location",
                    field=geo_point_field(null=True),
                ),
            ],
        ),
    ]
