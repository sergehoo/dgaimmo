# ContactRequest : demandes de contact depuis la landing page

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("full_name", models.CharField(max_length=180, verbose_name="Nom complet")),
                ("email", models.EmailField(db_index=True, max_length=254, verbose_name="Email")),
                ("phone", models.CharField(blank=True, max_length=32, verbose_name="Téléphone")),
                ("organization", models.CharField(blank=True, max_length=180, verbose_name="Organisation / Mutuelle")),
                (
                    "subject",
                    models.CharField(
                        choices=[
                            ("info", "Demande d'information"),
                            ("demo", "Demande de démo"),
                            ("partnership", "Partenariat"),
                            ("support", "Support technique"),
                            ("other", "Autre"),
                        ],
                        db_index=True,
                        default="info",
                        max_length=24,
                        verbose_name="Sujet",
                    ),
                ),
                ("message", models.TextField(verbose_name="Message")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "Nouvelle"),
                            ("in_progress", "En traitement"),
                            ("resolved", "Résolue"),
                            ("spam", "Spam / ignorée"),
                        ],
                        db_index=True,
                        default="new",
                        max_length=24,
                        verbose_name="Statut",
                    ),
                ),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "processed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contact_requests_processed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="core_contac_status_idx"),
                    models.Index(fields=["email", "created_at"], name="core_contac_email_idx"),
                ],
            },
        ),
    ]
