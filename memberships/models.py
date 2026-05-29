from django.db import models

from core.fields import geo_point_field
from core.models import TenantModel, TimeStampedModel


class Bank(TimeStampedModel):
    """Banque affiliée référencée par les membres (et plus tard partenaires programmes).

    Mutualisée au niveau plateforme : un membre choisit une banque parmi
    celles enregistrées par le SuperAdmin, ce qui permet d'agréger la
    concentration bancaire au niveau mutuelle/programme."""

    name = models.CharField("Nom de la banque", max_length=180, db_index=True)
    code = models.CharField("Code/abréviation", max_length=24, blank=True, db_index=True)
    country = models.CharField(max_length=2, default="CI", db_index=True)
    website = models.URLField(blank=True)
    is_partner = models.BooleanField(
        "Partenaire programme",
        default=False,
        db_index=True,
        help_text="Banque partenaire offrant des produits prêt immobilier.",
    )
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["country", "active"])]

    def __str__(self):
        return self.name


class Member(TenantModel):
    """Profil mutualiste complet : identité, situation familiale, profession,
    revenus déclarés et banque affiliée."""

    class Status(models.TextChoices):
        PROSPECT = "prospect", "Prospect"
        ACTIVE = "active", "Actif"
        DELINQUENT = "delinquent", "En retard"
        SUSPENDED = "suspended", "Suspendu"

    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "Célibataire"
        MARRIED = "married", "Marié(e)"
        DIVORCED = "divorced", "Divorcé(e)"
        WIDOWED = "widowed", "Veuf / Veuve"
        UNION_LIBRE = "union_libre", "Union libre"
        OTHER = "other", "Autre"

    class Gender(models.TextChoices):
        MALE = "male", "Masculin"
        FEMALE = "female", "Féminin"
        OTHER = "other", "Autre"

    # ---- Compte utilisateur lié & code ----
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="member_profile",
    )
    member_code = models.CharField(max_length=40, db_index=True)

    # ---- Identité ----
    first_name = models.CharField("Prénom(s)", max_length=120)
    last_name = models.CharField("Nom", max_length=120)
    phone = models.CharField("Téléphone", max_length=32, db_index=True)
    email = models.EmailField("Email contact", blank=True, db_index=True)
    birth_date = models.DateField("Date de naissance", null=True, blank=True)
    birth_place = models.CharField("Lieu de naissance", max_length=160, blank=True)
    gender = models.CharField("Genre", max_length=20, choices=Gender.choices, blank=True)
    national_id = models.CharField("CNI / Passeport", max_length=80, blank=True, db_index=True)
    photo = models.ImageField(upload_to="members/photos/", null=True, blank=True)
    qr_token = models.CharField(max_length=120, unique=True, db_index=True)

    # ---- Situation familiale ----
    marital_status = models.CharField(
        "Situation matrimoniale",
        max_length=24,
        choices=MaritalStatus.choices,
        default=MaritalStatus.SINGLE,
        db_index=True,
    )
    dependents_count = models.PositiveSmallIntegerField(
        "Nombre de personnes à charge",
        default=0,
        help_text="Enfants, conjoint(s), parents à charge...",
    )
    spouse_name = models.CharField("Nom du conjoint", max_length=180, blank=True)

    # ---- Vie professionnelle ----
    employer = models.CharField("Entreprise / employeur", max_length=180, blank=True)
    job_function = models.CharField("Fonction dans l'entreprise", max_length=160, blank=True)
    professional_seniority_months = models.PositiveIntegerField(
        "Ancienneté (mois)",
        default=0,
        help_text="Ancienneté totale dans le poste / l'entreprise.",
    )
    hire_date = models.DateField("Date d'embauche", null=True, blank=True)

    # ---- Banque affiliée ----
    bank = models.ForeignKey(
        Bank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affiliated_members",
        verbose_name="Banque affiliée",
    )
    bank_account_number = models.CharField("Numéro de compte / IBAN", max_length=64, blank=True)

    # ---- Objectifs immobiliers personnels ----
    # Le membre déclare ses propres ambitions (terrain, maison, immeuble…).
    # La mutuelle agrège ces valeurs pour piloter ses choix de programme.
    real_estate_objective = models.JSONField(
        "Objectifs immobiliers du membre",
        default=list,
        blank=True,
        help_text="Liste des objectifs immobiliers visés par ce membre (sélection multiple).",
    )

    # ---- Statut & onboarding ----
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PROSPECT, db_index=True
    )
    joined_at = models.DateField(null=True, blank=True, db_index=True)
    location = geo_point_field(null=True)
    kyc_validated = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("mutuelle", "member_code")]
        indexes = [
            models.Index(fields=["mutuelle", "status"]),
            models.Index(fields=["mutuelle", "phone"]),
            models.Index(fields=["mutuelle", "kyc_validated"]),
            models.Index(fields=["mutuelle", "marital_status"]),
            models.Index(fields=["mutuelle", "bank"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        if not self.birth_date:
            return None
        from datetime import date

        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def seniority_years(self):
        return round((self.professional_seniority_months or 0) / 12, 1)

    @property
    def real_estate_objectives_labels(self) -> list:
        """Libellés humains des objectifs immobiliers du membre."""
        # Choices alignées sur Mutuelle.RealEstateObjective
        choices = {
            "terrain": "Terrain",
            "maison": "Maison / villa",
            "immeuble": "Immeuble",
            "appartement": "Appartement",
            "logement_social": "Logement social",
            "programme_promoteur": "Programme promoteur",
            "construction_collective": "Construction collective",
            "autre": "Autre objectif",
        }
        return [choices.get(v, v) for v in (self.real_estate_objective or [])]

    @property
    def real_estate_objectives_display(self) -> str:
        return " · ".join(self.real_estate_objectives_labels)


class Beneficiary(TenantModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="beneficiaries")
    full_name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=60)
    birth_date = models.DateField(null=True, blank=True)
    kyc_document = models.FileField(upload_to="beneficiaries/kyc/", null=True, blank=True)


class KYCDocument(TenantModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="kyc_documents")
    document_type = models.CharField(max_length=80, db_index=True)
    file = models.FileField(upload_to="members/kyc/")
    verified = models.BooleanField(default=False, db_index=True)
    ocr_payload = models.JSONField(default=dict, blank=True)
