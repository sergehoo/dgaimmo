from django.core.validators import MinValueValidator
from django.db import models

from core.fields import geo_point_field
from core.models import TimeStampedModel


class Mutuelle(TimeStampedModel):
    """Tenant racine de la plateforme MutuelleX.

    Chaque mutuelle est isolée et porte les informations d'onboarding
    nécessaires au scoring, à la gouvernance et au workflow immobilier.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PENDING = "pending", "En validation"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspendue"

    class RealEstateObjective(models.TextChoices):
        TERRAIN = "terrain", "Terrain"
        MAISON = "maison", "Maison / villa"
        IMMEUBLE = "immeuble", "Immeuble"
        APPARTEMENT = "appartement", "Appartement"
        LOGEMENT_SOCIAL = "logement_social", "Logement social"
        PROGRAMME_PROMOTEUR = "programme_promoteur", "Programme promoteur"
        CONSTRUCTION_COLLECTIVE = "construction_collective", "Construction collective"
        AUTRE = "autre", "Autre objectif"

    class OrganizationType(models.TextChoices):
        ENTREPRISE = "entreprise", "Entreprise"
        ASSOCIATION = "association", "Association"
        COOPERATIVE = "cooperative", "Coopérative"
        COMMUNAUTE = "communaute", "Communauté"
        ADMINISTRATION = "administration", "Administration"
        GROUPE_INFORMEL = "groupe_informel", "Groupe informel"
        AUTRE = "autre", "Autre"

    # Identité de la mutuelle
    name = models.CharField("Nom de la mutuelle", max_length=180, db_index=True)
    slug = models.SlugField(unique=True)
    legal_name = models.CharField("Raison sociale", max_length=180, blank=True)

    # Organisation / entreprise porteuse
    organization_name = models.CharField(
        "Entreprise / organisation",
        max_length=180,
        blank=True,
        help_text="Entité juridique, association, communauté ou groupe à l'origine de la mutuelle.",
    )
    organization_type = models.CharField(
        "Type d'organisation",
        max_length=32,
        choices=OrganizationType.choices,
        default=OrganizationType.AUTRE,
        db_index=True,
    )

    # Données métier d'onboarding
    estimated_members_count = models.PositiveIntegerField(
        "Nombre estimé de membres",
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Estimation initiale pour dimensionner la mutuelle et le scoring.",
    )
    real_estate_objective = models.JSONField(
        "Objectifs immobiliers",
        default=list,
        blank=True,
        help_text="Liste des objectifs immobiliers visés (sélection multiple).",
    )
    real_estate_objective_details = models.TextField(
        "Précisions sur l'objectif immobilier",
        blank=True,
        help_text="Décrivez librement le projet (zone, budget cible, calendrier...).",
    )

    # Contact référent de la mutuelle
    contact_last_name = models.CharField("NOM du contact", max_length=120, blank=True)
    contact_first_name = models.CharField("Prénom(s) du contact", max_length=120, blank=True)
    contact_function = models.CharField(
        "Fonction du contact",
        max_length=120,
        blank=True,
        help_text="Fonction au sein de l'organisation (Président, DG, RH, Trésorier...).",
    )
    contact_email = models.EmailField("Email du contact", blank=True, db_index=True)
    contact_phone = models.CharField("Téléphone du contact", max_length=32, blank=True)

    # Localisation et SaaS
    country = models.CharField(max_length=2, default="CI", db_index=True)
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    logo = models.ImageField(upload_to="mutuelles/logos/", blank=True, null=True)
    primary_color = models.CharField(max_length=16, default="#0f766e")
    accent_color = models.CharField(max_length=16, default="#f59e0b")
    subscription_plan = models.CharField(max_length=60, default="starter", db_index=True)
    custom_domain = models.CharField(max_length=180, blank=True, db_index=True)
    headquarters_location = geo_point_field(null=True)
    business_rules = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["country", "status"]),
            models.Index(fields=["subscription_plan", "status"]),
            # Note : pas d'index composite sur real_estate_objective car
            # c'est un JSONField (liste). Un index GIN PostgreSQL pourrait
            # être ajouté ultérieurement via une RunSQL pour les filtres
            # par contenu : CREATE INDEX ... USING GIN (real_estate_objective).
            models.Index(fields=["organization_type", "status"]),
        ]

    def __str__(self):
        return self.name

    @property
    def contact_full_name(self) -> str:
        parts = [self.contact_last_name.upper(), self.contact_first_name]
        return " ".join(part for part in parts if part).strip()

    @property
    def real_estate_objectives_display(self) -> str:
        """Rend la liste d'objectifs immobiliers en libellés humains, séparés par ' · '."""
        values = self.real_estate_objective or []
        mapping = dict(self.RealEstateObjective.choices)
        return " · ".join(mapping.get(v, v) for v in values)

    @property
    def real_estate_objectives_labels(self) -> list:
        """Retourne la liste des libellés humains (pratique pour itérer en template)."""
        mapping = dict(self.RealEstateObjective.choices)
        return [mapping.get(v, v) for v in (self.real_estate_objective or [])]


class MutuelleMembership(TimeStampedModel):
    mutuelle = models.ForeignKey(Mutuelle, on_delete=models.CASCADE, related_name="staff_memberships")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="mutuelle_memberships")
    role = models.CharField(max_length=32, db_index=True)
    permissions = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("mutuelle", "user")]
        indexes = [models.Index(fields=["mutuelle", "role", "active"])]
