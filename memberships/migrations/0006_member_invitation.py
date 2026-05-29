# MemberInvitation : invitation par email pour auto-onboarding

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import memberships.models


class Migration(migrations.Migration):

    dependencies = [
        ("memberships", "0005_member_real_estate_objective"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(db_index=True, max_length=254, verbose_name="Email du prospect")),
                ("full_name", models.CharField(blank=True, help_text="Pré-remplit le formulaire d'inscription du prospect.", max_length=180, verbose_name="Nom complet (optionnel)")),
                (
                    "token",
                    models.CharField(
                        db_index=True,
                        default=memberships.models._generate_invitation_token,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("sent", "Envoyée"),
                            ("accepted", "Acceptée"),
                            ("expired", "Expirée"),
                            ("cancelled", "Annulée"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("message", models.TextField(blank=True, verbose_name="Message personnalisé")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "mutuelle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="memberinvitations",
                        to="mutuelles.mutuelle",
                    ),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="member_invitations_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        blank=True,
                        help_text="Membre créé lorsque l'invitation est acceptée.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_from_invitation",
                        to="memberships.member",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["mutuelle", "created_at"], name="memberships_minv_mut_ca_idx"),
                    models.Index(fields=["mutuelle", "status"], name="memberships_minv_mut_st_idx"),
                    models.Index(fields=["mutuelle", "email"], name="memberships_minv_mut_em_idx"),
                ],
            },
        ),
    ]
