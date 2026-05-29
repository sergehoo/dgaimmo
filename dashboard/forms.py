import uuid

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.text import slugify

from ai_engine.models import AIAnalysis
from accounts.models import OTPChallenge
from claims.models import AssistanceClaim
from contributions.models import Contribution, ContributionPlan
from governance.models import GeneralAssembly, Resolution
from memberships.models import Bank, Member
from mutuelles.models import Mutuelle
from payments.models import Payment
from notifications.models import Notification
from real_estate.models import (
    FinancingScenario,
    MemberFinancialProfile,
    MortgageApplication,
    PropertyDocument,
    PropertyLot,
    PropertyReservation,
    RealEstateOpportunity,
    RealEstateProgram,
)


BASE_INPUT = "min-h-12 w-full rounded-xl border border-[#dbe6f5] bg-white px-4 text-sm font-bold outline-none focus:border-[#0b55d9]"
BASE_SELECT = BASE_INPUT
BASE_TEXTAREA = "min-h-28 w-full rounded-xl border border-[#dbe6f5] bg-white px-4 py-3 text-sm font-bold outline-none focus:border-[#0b55d9]"
COLOR_INPUT = "h-12 w-16 cursor-pointer rounded-xl border border-[#dbe6f5] bg-white p-1 outline-none focus:border-[#0b55d9]"


class ColorInput(forms.TextInput):
    """Widget HTML5 <input type=color> (absent en standard Django jusqu'à 5.x)."""

    input_type = "color"


# Compat ascendante : certains modules référencent forms.ColorInput
if not hasattr(forms, "ColorInput"):
    forms.ColorInput = ColorInput


class StyledModelForm(forms.ModelForm):
    def _style_fields(self):
        for name, field in self.fields.items():
            widget = field.widget
            # Multi-checkboxes & radio : on laisse le rendu natif (le template gère)
            if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            # Case à cocher unique : pas de class plein-input
            if isinstance(widget, forms.CheckboxInput):
                continue
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", BASE_TEXTAREA)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", BASE_SELECT)
            elif isinstance(widget, ColorInput) or name in {"primary_color", "accent_color"}:
                field.widget = ColorInput(attrs={**widget.attrs, "class": COLOR_INPUT})
            else:
                widget.attrs.setdefault("class", BASE_INPUT)


class UserProfileForm(StyledModelForm):
    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name", "email", "phone"]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Email",
            "phone": "Téléphone",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError("Cet email est déjà utilisé par un autre compte.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return phone
        User = get_user_model()
        if User.objects.exclude(pk=self.instance.pk).filter(phone=phone).exists():
            raise forms.ValidationError("Ce téléphone est déjà utilisé par un autre compte.")
        return phone

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.email = instance.email.strip().lower()
        instance.username = instance.email
        if commit:
            instance.save()
        return instance


class UserPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "old_password": "Mot de passe actuel",
            "new_password1": "Nouveau mot de passe",
            "new_password2": "Confirmer le nouveau mot de passe",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)
            field.widget.attrs.setdefault("class", BASE_INPUT)


class MutuelleCreateForm(StyledModelForm):
    """Formulaire admin pour créer une mutuelle depuis la console.

    Implémente le workflow d'onboarding avec :
    - identité (nom, organisation porteuse)
    - dimensionnement (membres estimés, objectif immobilier)
    - contact référent (NOM, prénoms, fonction, email)
    - branding et localisation
    """

    class Meta:
        model = Mutuelle
        # Note : `legal_name`, `country`, `currency` sont EXCLUS du formulaire.
        # - legal_name : blank=True dans le modèle, modifiable ultérieurement
        #   via l'écran branding/identité.
        # - country / currency : prennent leurs défauts modèle (CI / XOF).
        fields = [
            "name",
            "organization_name",
            "organization_type",
            "estimated_members_count",
            "real_estate_objective",
            "real_estate_objective_details",
            "contact_last_name",
            "contact_first_name",
            "contact_function",
            "contact_email",
            "contact_phone",
            "primary_color",
            "accent_color",
        ]
        labels = {
            "name": "Nom de la mutuelle",
            "organization_name": "Entreprise / organisation",
            "organization_type": "Type d'organisation",
            "estimated_members_count": "Nombre estimé de membres",
            "real_estate_objective": "Objectif immobilier",
            "real_estate_objective_details": "Précisions sur l'objectif",
            "contact_last_name": "NOM du contact",
            "contact_first_name": "Prénom(s) du contact",
            "contact_function": "Fonction",
            "contact_email": "Email du contact",
            "contact_phone": "Téléphone du contact",
            "primary_color": "Couleur principale",
            "accent_color": "Couleur secondaire",
        }
        widgets = {
            "primary_color": ColorInput,
            "accent_color": ColorInput,
            "real_estate_objective_details": forms.Textarea(attrs={"rows": 3}),
            "estimated_members_count": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Le JSONField est rendu par défaut comme un textarea JSON brut.
        # On le remplace par un MultipleChoiceField avec cases à cocher.
        self.fields["real_estate_objective"] = forms.MultipleChoiceField(
            label="Objectifs immobiliers",
            choices=Mutuelle.RealEstateObjective.choices,
            widget=forms.CheckboxSelectMultiple(attrs={"class": "mx-objective-checkboxes"}),
            required=True,
            help_text="Sélectionnez un ou plusieurs objectifs poursuivis collectivement par la mutuelle.",
        )
        # Pré-remplissage : si on édite une instance existante, restaurer la liste
        instance = kwargs.get("instance") or getattr(self, "instance", None)
        if instance and isinstance(getattr(instance, "real_estate_objective", None), list):
            self.initial["real_estate_objective"] = instance.real_estate_objective

        # Champs marqués requis pour ce workflow d'onboarding
        for required_name in (
            "organization_name",
            "estimated_members_count",
            "real_estate_objective",
            "contact_last_name",
            "contact_first_name",
            "contact_function",
            "contact_email",
        ):
            if required_name in self.fields:
                self.fields[required_name].required = True
        self._style_fields()
        # Placeholder UX premium
        placeholders = {
            "name": "Ex. Mutuelle Habitat Cocody",
            "organization_name": "Ex. MutuelleX SARL",
            "estimated_members_count": "Ex. 250",
            "contact_last_name": "OGAH",
            "contact_first_name": "Serge",
            "contact_function": "Président, DG, Trésorier...",
            "contact_email": "contact@organisation.ci",
            "contact_phone": "+225 07 00 00 00 00",
            "real_estate_objective_details": "Zone visée, type de bien, budget, calendrier...",
        }
        for name, placeholder in placeholders.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("placeholder", placeholder)

    def clean_real_estate_objective(self):
        # MultipleChoiceField renvoie une list[str] — assure une liste propre
        values = self.cleaned_data.get("real_estate_objective") or []
        return list(values)

    def clean_contact_email(self):
        return self.cleaned_data["contact_email"].strip().lower()

    def clean_contact_last_name(self):
        return self.cleaned_data["contact_last_name"].strip().upper()

    def clean_contact_first_name(self):
        value = self.cleaned_data["contact_first_name"].strip()
        return " ".join(part.capitalize() for part in value.split())

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not slugify(name):
            raise forms.ValidationError("Le nom doit contenir au moins une lettre ou un chiffre.")
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        base_slug = slugify(instance.name)
        slug = base_slug
        index = 2
        while Mutuelle.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
            slug = f"{base_slug}-{index}"
            index += 1
        instance.slug = slug
        if not instance.status:
            instance.status = Mutuelle.Status.ACTIVE
        if commit:
            instance.save()
        return instance


class PublicMutuelleSignupForm(forms.Form):
    """Workflow public en une étape : crée la mutuelle, le compte admin
    et capture les informations métier (organisation, dimensionnement,
    objectif immobilier, contact référent)."""

    # ---- Bloc Mutuelle ----
    mutuelle_name = forms.CharField(label="Nom de la mutuelle", max_length=180)
    organization_name = forms.CharField(
        label="Entreprise / organisation",
        max_length=180,
        help_text="Société, association, communauté ou groupe porteur de la mutuelle.",
    )
    organization_type = forms.ChoiceField(
        label="Type d'organisation",
        choices=Mutuelle.OrganizationType.choices,
        initial=Mutuelle.OrganizationType.ENTREPRISE,
    )
    estimated_members_count = forms.IntegerField(
        label="Nombre estimé de membres",
        min_value=1,
        help_text="Estimation initiale pour dimensionner la mutuelle.",
        widget=forms.NumberInput(attrs={"min": "1", "step": "1"}),
    )
    real_estate_objective = forms.MultipleChoiceField(
        label="Objectifs immobiliers",
        choices=Mutuelle.RealEstateObjective.choices,
        initial=[Mutuelle.RealEstateObjective.TERRAIN],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "mx-objective-checkboxes"}),
        help_text="Sélectionnez un ou plusieurs objectifs poursuivis collectivement par la mutuelle.",
    )
    real_estate_objective_details = forms.CharField(
        label="Précisions sur l'objectif",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Zone visée, type de bien, budget, calendrier..."}),
    )
    # Note : country et currency utilisent les défauts du modèle (CI / XOF),
    # paramétrables ensuite via l'écran branding/identité.
    primary_color = forms.CharField(
        label="Couleur principale",
        max_length=16,
        initial="#003b98",
        widget=ColorInput(attrs={"class": COLOR_INPUT}),
    )

    # ---- Bloc Contact référent ----
    last_name = forms.CharField(label="NOM", max_length=150, help_text="Nom de famille du contact (sera mis en majuscules).")
    first_name = forms.CharField(label="Prénom(s)", max_length=150)
    contact_function = forms.CharField(
        label="Fonction",
        max_length=120,
        help_text="Fonction au sein de l'organisation (Président, DG, Trésorier...).",
    )
    email = forms.EmailField(label="Email du contact")
    phone = forms.CharField(label="Téléphone (Mobile Money)", max_length=32, required=False)

    # ---- Bloc Sécurité ----
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if name == "primary_color":
                continue
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", BASE_TEXTAREA)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", BASE_SELECT)
            else:
                widget.attrs.setdefault("class", BASE_INPUT)
        # Placeholders UX
        self.fields["mutuelle_name"].widget.attrs.setdefault("placeholder", "Ex. Mutuelle Habitat Cocody")
        self.fields["organization_name"].widget.attrs.setdefault("placeholder", "Ex. SocieteX SARL")
        self.fields["estimated_members_count"].widget.attrs.setdefault("placeholder", "Ex. 250")
        self.fields["last_name"].widget.attrs.setdefault("placeholder", "OGAH")
        self.fields["first_name"].widget.attrs.setdefault("placeholder", "Serge")
        self.fields["contact_function"].widget.attrs.setdefault("placeholder", "Président, DG, Trésorier...")
        self.fields["email"].widget.attrs.setdefault("placeholder", "contact@organisation.ci")
        self.fields["phone"].widget.attrs.setdefault("placeholder", "+225 07 00 00 00 00")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet email.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return phone
        User = get_user_model()
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("Un compte existe déjà avec ce téléphone.")
        return phone

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip().upper()

    def clean_first_name(self):
        value = self.cleaned_data["first_name"].strip()
        return " ".join(part.capitalize() for part in value.split())

    def clean_contact_function(self):
        return self.cleaned_data["contact_function"].strip()

    def clean_organization_name(self):
        return self.cleaned_data["organization_name"].strip()

    def clean_mutuelle_name(self):
        name = self.cleaned_data["mutuelle_name"].strip()
        base_slug = slugify(name)
        if not base_slug:
            raise forms.ValidationError("Le nom doit contenir au moins une lettre ou un chiffre.")
        if Mutuelle.objects.filter(slug=base_slug).exists():
            raise forms.ValidationError("Une mutuelle avec ce nom existe déjà. Ajoutez une précision au nom.")
        return name

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Les mots de passe ne correspondent pas.")
        if password1:
            validate_password(password1)
        return cleaned

    def save(self):
        User = get_user_model()
        data = self.cleaned_data
        mutuelle = Mutuelle.objects.create(
            name=data["mutuelle_name"],
            organization_name=data["organization_name"],
            organization_type=data["organization_type"],
            estimated_members_count=data["estimated_members_count"],
            # MultipleChoiceField → list[str]
            real_estate_objective=list(data["real_estate_objective"] or []),
            real_estate_objective_details=data.get("real_estate_objective_details", ""),
            contact_last_name=data["last_name"],
            contact_first_name=data["first_name"],
            contact_function=data["contact_function"],
            contact_email=data["email"],
            contact_phone=data.get("phone") or "",
            slug=slugify(data["mutuelle_name"]),
            # country (CI) et currency (XOF) : défauts du modèle
            primary_color=data["primary_color"],
            accent_color="#0bbf63",
            status=Mutuelle.Status.ACTIVE,
        )
        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password1"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data.get("phone") or None,
            role=User.Role.MUTUELLE_ADMIN,
            default_mutuelle=mutuelle,
        )
        return mutuelle, user


class MutuelleBrandingForm(StyledModelForm):
    class Meta:
        model = Mutuelle
        fields = ["name", "legal_name", "primary_color", "accent_color", "logo"]
        labels = {
            "name": "Nom public",
            "legal_name": "Raison sociale",
            "primary_color": "Couleur principale",
            "accent_color": "Couleur accent",
            "logo": "Logo",
        }
        widgets = {
            "primary_color": ColorInput,
            "accent_color": ColorInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class MemberCreateForm(StyledModelForm):
    """Workflow complet de création membre.

    Bloc 1 — Identité : nom, prénoms, email, téléphone, date de naissance, genre
    Bloc 2 — Vie pro : entreprise, fonction, date d'embauche, ancienneté
    Bloc 3 — Famille : situation matrimoniale, conjoint, personnes à charge
    Bloc 4 — Bancaire : banque affiliée, numéro de compte
    Bloc 5 — Adhésion : statut, KYC
    """

    class Meta:
        model = Member
        # Note : `status` et `kyc_validated` sont volontairement EXCLUS du
        # formulaire d'enrôlement. Ils prennent leurs valeurs par défaut au
        # niveau modèle (status=PROSPECT, kyc_validated=False) et sont
        # modifiés ensuite via les écrans dédiés (workflow KYC, gestion
        # statut adhésion).
        # Note : les champs "vie professionnelle" (employer, job_function,
        # hire_date, professional_seniority_months) restent dans le modèle
        # mais sont retirés du formulaire d'enrôlement initial. Ils peuvent
        # être saisis ensuite via les écrans dédiés (profil financier).
        fields = [
            "member_code",
            # Identité
            "first_name",
            "last_name",
            "phone",
            "email",
            "birth_date",
            "birth_place",
            "gender",
            "national_id",
            # Famille
            "marital_status",
            "spouse_name",
            "dependents_count",
            # Banque
            "bank",
            "bank_account_number",
            # Objectifs immobiliers personnels (multi-select)
            "real_estate_objective",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "dependents_count": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "member_code": "Code membre",
            "first_name": "Prénom(s)",
            "last_name": "NOM",
            "phone": "Téléphone",
            "email": "Email contact",
            "birth_date": "Date de naissance",
            "birth_place": "Lieu de naissance",
            "gender": "Genre",
            "national_id": "CNI / Passeport",
            "marital_status": "Situation matrimoniale",
            "spouse_name": "Nom du conjoint",
            "dependents_count": "Personnes à charge",
            "bank": "Banque affiliée",
            "bank_account_number": "Numéro de compte / IBAN",
            "real_estate_objective": "Objectifs immobiliers personnels",
        }

    def __init__(self, *args, mutuelle=None, **kwargs):
        """
        Args:
            mutuelle: Mutuelle d'affectation (auto-injectée par la vue depuis
                request.mutuelle ou request.user.default_mutuelle).
        """
        super().__init__(*args, **kwargs)
        self._mutuelle = mutuelle
        self.fields["member_code"].required = False
        self.fields["member_code"].help_text = "Laissez vide pour générer un code automatiquement."
        # Banques actives uniquement
        self.fields["bank"].queryset = Bank.objects.filter(active=True).order_by("name")
        self.fields["bank"].required = False
        self.fields["bank"].empty_label = "— Aucune / non renseignée —"

        # JSONField rendu en MultipleChoiceField (checkboxes) — choices
        # alignées sur celles de Mutuelle.RealEstateObjective pour cohérence.
        self.fields["real_estate_objective"] = forms.MultipleChoiceField(
            label="Objectifs immobiliers personnels",
            choices=Mutuelle.RealEstateObjective.choices,
            widget=forms.CheckboxSelectMultiple(attrs={"class": "mx-objective-checkboxes"}),
            required=False,
            help_text="Que vise ce membre à terme ? (sélection multiple)",
        )
        instance = kwargs.get("instance") or getattr(self, "instance", None)
        if instance and isinstance(getattr(instance, "real_estate_objective", None), list):
            self.initial["real_estate_objective"] = instance.real_estate_objective

        # Champs requis pour le workflow
        for required in ("first_name", "last_name", "phone"):
            self.fields[required].required = True
        # Placeholders premium
        placeholders = {
            "first_name": "Serge",
            "last_name": "OGAH",
            "phone": "+225 07 00 00 00 00",
            "email": "membre@email.ci",
            "birth_place": "Abidjan, CI",
            "national_id": "CI001234567",
            "spouse_name": "Nom et prénoms du conjoint",
            "bank_account_number": "CI93 CI16 0103 0000 0000 0000 0000",
        }
        for name, ph in placeholders.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("placeholder", ph)
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        if not self._mutuelle:
            raise forms.ValidationError(
                "Aucune mutuelle active n'est rattachée à votre compte. "
                "Sélectionnez ou créez une mutuelle avant d'enrôler un membre."
            )
        return cleaned

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip().upper()

    def clean_first_name(self):
        value = self.cleaned_data["first_name"].strip()
        return " ".join(part.capitalize() for part in value.split())

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        return email

    def clean_real_estate_objective(self):
        values = self.cleaned_data.get("real_estate_objective") or []
        return list(values)

    def _generate_member_code(self, mutuelle):
        slug_prefix = "".join(char for char in mutuelle.slug.upper() if char.isalnum())[:4] or "MEMB"
        year = timezone.now().year
        base = f"{slug_prefix}-{year}"
        sequence = Member.all_objects.filter(mutuelle=mutuelle, member_code__startswith=base).count() + 1
        while True:
            candidate = f"{base}-{sequence:04d}"
            if not Member.all_objects.filter(mutuelle=mutuelle, member_code=candidate).exists():
                return candidate
            sequence += 1

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Mutuelle injectée par la vue (jamais saisie par l'utilisateur)
        if self._mutuelle and not instance.mutuelle_id:
            instance.mutuelle = self._mutuelle
        instance.member_code = (instance.member_code or "").strip().upper()
        if not instance.member_code:
            instance.member_code = self._generate_member_code(instance.mutuelle)
        instance.qr_token = f"qr-{instance.member_code.lower()}-{uuid.uuid4().hex[:8]}"
        if not instance.joined_at:
            instance.joined_at = timezone.now().date()
        if commit:
            instance.save()
        return instance


class FinancialProfileForm(StyledModelForm):
    """Profil financier : revenus, charges, dettes, situation pro.

    Le membre est injecté par la vue (kwarg `member=`) — l'utilisateur ne
    le sélectionne JAMAIS depuis ce formulaire. La saisie est contextuelle :
    elle se fait depuis la fiche du membre. Cela évite les erreurs de
    rattachement et garantit l'isolation tenant.
    """

    class Meta:
        model = MemberFinancialProfile
        fields = [
            # Revenus
            "net_monthly_salary",
            "complementary_income",
            "pensions",
            # Charges
            "fixed_charges",
            "existing_loan_payments",
            "other_debts",
            "pensions_paid",
            "mutual_contributions",
            # Situation
            "dependents_count",
            "professional_seniority_months",
            "contract_type",
            "employment_type",
            "risk_level",
        ]
        widgets = {
            "net_monthly_salary": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "complementary_income": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "pensions": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "fixed_charges": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "existing_loan_payments": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "other_debts": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "pensions_paid": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "mutual_contributions": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "dependents_count": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "professional_seniority_months": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "net_monthly_salary": "Revenu mensuel net",
            "complementary_income": "Revenus complémentaires",
            "pensions": "Pensions reçues",
            "fixed_charges": "Charges mensuelles fixes",
            "existing_loan_payments": "Prêts en cours (mensualité)",
            "other_debts": "Autres dettes mensualisées",
            "pensions_paid": "Pensions versées",
            "mutual_contributions": "Cotisations mutuelle",
            "dependents_count": "Personnes à charge",
            "professional_seniority_months": "Ancienneté (mois)",
            "contract_type": "Type de contrat",
            "employment_type": "Statut professionnel",
            "risk_level": "Niveau de risque",
        }

    def __init__(self, *args, member=None, **kwargs):
        """
        Args:
            member: Membre auquel rattacher le profil financier. Doit être
                fourni par la vue (depuis ?member_id= ou contexte).
        """
        super().__init__(*args, **kwargs)
        self._member = member
        # Pré-remplit dependents_count et ancienneté depuis la fiche membre
        if member is not None:
            self.initial.setdefault("dependents_count", member.dependents_count or 0)
            self.initial.setdefault(
                "professional_seniority_months", member.professional_seniority_months or 0
            )
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        if not self._member:
            raise forms.ValidationError(
                "Aucun membre cible n'est fourni. Ouvrez le profil financier depuis "
                "la fiche du membre."
            )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Rattachement automatique au membre + mutuelle (jamais saisi)
        if self._member is not None:
            instance.member = self._member
            instance.mutuelle = self._member.mutuelle
        if commit:
            instance.save()
        return instance


class ProjectCreateForm(forms.Form):
    mutuelle = forms.ModelChoiceField(queryset=Mutuelle.objects.all(), label="Mutuelle")
    program_name = forms.CharField(label="Nom du programme", max_length=180)
    city = forms.CharField(label="Ville", max_length=120)
    total_lots = forms.IntegerField(label="Nombre total de lots", min_value=1, initial=20)
    opportunity_title = forms.CharField(label="Titre de l'opportunité", max_length=180)
    property_type = forms.ChoiceField(label="Type de bien", choices=RealEstateOpportunity.PropertyType.choices)
    amount = forms.DecimalField(label="Prix du bien", max_digits=14, decimal_places=2)
    initial_deposit = forms.DecimalField(label="Apport initial", max_digits=14, decimal_places=2, initial=0)
    financing_months = forms.IntegerField(label="Durée financement (mois)", min_value=1, initial=120)
    lots_to_create = forms.IntegerField(label="Lots à générer", min_value=1, max_value=50, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_SELECT if isinstance(field.widget, forms.Select) else BASE_INPUT)


class SimulationCreateForm(forms.Form):
    """Formulaire de simulation de quotité cessible.

    Le membre est injecté par la vue (kwarg `member=`) — l'utilisateur ne
    le sélectionne JAMAIS depuis ce formulaire. Le contexte d'appel est
    toujours explicite (depuis la fiche du membre ou un workflow).
    """

    requested_amount = forms.DecimalField(label="Montant demandé", max_digits=14, decimal_places=2)
    requested_duration_months = forms.IntegerField(label="Période d'amortissement (mois)", min_value=1, initial=120)
    annual_interest_rate = forms.DecimalField(label="Taux annuel (%)", max_digits=5, decimal_places=2, initial=7)
    max_debt_ratio = forms.DecimalField(label="Taux d'endettement max (%)", max_digits=5, decimal_places=2, initial=33)

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._member = member
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                BASE_SELECT if isinstance(field.widget, forms.Select) else BASE_INPUT,
            )

    def clean(self):
        cleaned = super().clean()
        if not self._member:
            raise forms.ValidationError(
                "Aucun membre cible n'est fourni. Ouvrez la simulation depuis "
                "la fiche du membre."
            )
        cleaned["member"] = self._member
        return cleaned


class FinancingScenarioCreateForm(forms.Form):
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre")
    opportunity = forms.ModelChoiceField(queryset=RealEstateOpportunity.all_objects.select_related("program"), label="Opportunité")
    mode = forms.ChoiceField(label="Mode de financement", choices=FinancingScenario.Mode.choices)
    personal_deposit = forms.DecimalField(label="Apport personnel", max_digits=14, decimal_places=2, initial=0)
    duration_months = forms.IntegerField(label="Période d'amortissement (mois)", min_value=1, initial=120)
    annual_interest_rate = forms.DecimalField(label="Taux annuel (%)", max_digits=5, decimal_places=2, initial=7)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_SELECT if isinstance(field.widget, forms.Select) else BASE_INPUT)


class MortgageApplicationCreateForm(StyledModelForm):
    scenario = forms.ModelChoiceField(queryset=FinancingScenario.all_objects.select_related("member", "opportunity"), label="Scénario")

    class Meta:
        model = MortgageApplication
        fields = ["scenario", "status", "committee_notes", "bank_reference", "disbursed_amount"]
        labels = {
            "status": "Statut",
            "committee_notes": "Notes comité",
            "bank_reference": "Référence banque",
            "disbursed_amount": "Montant décaissé",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ReservationCreateForm(StyledModelForm):
    lot = forms.ModelChoiceField(queryset=PropertyLot.all_objects.select_related("opportunity"), label="Lot")
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre")

    class Meta:
        model = PropertyReservation
        fields = ["lot", "member", "deposit_paid", "decision_notes"]
        labels = {"deposit_paid": "Acompte versé", "decision_notes": "Notes de décision"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ContributionPlanCreateForm(StyledModelForm):
    mutuelle = forms.ModelChoiceField(queryset=Mutuelle.objects.all(), label="Mutuelle")

    class Meta:
        model = ContributionPlan
        fields = ["mutuelle", "name", "frequency", "amount", "penalty_rate", "active"]
        labels = {
            "name": "Nom du plan",
            "frequency": "Fréquence",
            "amount": "Montant",
            "penalty_rate": "Pénalité retard (%)",
            "active": "Actif",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ContributionCreateForm(StyledModelForm):
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre")
    plan = forms.ModelChoiceField(queryset=ContributionPlan.all_objects.select_related("mutuelle"), label="Plan")

    class Meta:
        model = Contribution
        fields = ["member", "plan", "amount", "currency", "due_date", "status", "penalty_amount"]
        labels = {
            "amount": "Montant",
            "currency": "Devise",
            "due_date": "Date d'échéance",
            "status": "Statut",
            "penalty_amount": "Pénalité",
        }
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PaymentCreateForm(StyledModelForm):
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre")

    class Meta:
        model = Payment
        fields = ["member", "provider", "amount", "currency", "phone", "purpose"]
        labels = {"provider": "Canal", "amount": "Montant", "currency": "Devise", "phone": "Téléphone", "purpose": "Objet"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class AssistanceClaimCreateForm(StyledModelForm):
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre")

    class Meta:
        model = AssistanceClaim
        fields = [
            "member",
            "claim_type",
            "beneficiary_name",
            "incident_date",
            "amount",
            "currency",
            "description",
            "status",
            "approved_amount",
            "decision_notes",
        ]
        labels = {
            "claim_type": "Type d'assistance",
            "beneficiary_name": "Bénéficiaire",
            "incident_date": "Date de l'événement",
            "amount": "Montant demandé",
            "currency": "Devise",
            "description": "Description",
            "status": "Statut",
            "approved_amount": "Montant approuvé",
            "decision_notes": "Notes décision",
        }
        widgets = {"incident_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PropertyDocumentUploadForm(StyledModelForm):
    program = forms.ModelChoiceField(queryset=RealEstateProgram.all_objects.select_related("mutuelle"), label="Programme")

    class Meta:
        model = PropertyDocument
        fields = ["program", "document_type", "file", "verified"]
        labels = {"document_type": "Type de document", "file": "Fichier", "verified": "Document vérifié"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class NotificationCreateForm(StyledModelForm):
    mutuelle = forms.ModelChoiceField(queryset=Mutuelle.objects.all(), label="Mutuelle")
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre", required=False)

    class Meta:
        model = Notification
        fields = ["mutuelle", "member", "channel", "title", "body"]
        labels = {
            "channel": "Canal",
            "title": "Titre",
            "body": "Message",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class AIAnalysisCreateForm(StyledModelForm):
    mutuelle = forms.ModelChoiceField(queryset=Mutuelle.objects.all(), label="Mutuelle")

    class Meta:
        model = AIAnalysis
        fields = ["mutuelle", "provider", "prompt"]
        labels = {
            "provider": "Moteur IA",
            "prompt": "Instruction comité",
        }
        widgets = {
            "prompt": forms.Textarea(
                attrs={
                    "placeholder": "Ex: produire une note de décision pour financement collectif immobilier, risques de surendettement et recommandations banque."
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["prompt"].initial = "Produire une note de décision comité pour programme immobilier mutualiste."
        self._style_fields()


class GeneralAssemblyCreateForm(StyledModelForm):
    mutuelle = forms.ModelChoiceField(queryset=Mutuelle.objects.all(), label="Mutuelle")

    class Meta:
        model = GeneralAssembly
        fields = ["mutuelle", "title", "scheduled_at", "location", "online_url", "status", "quorum_required"]
        labels = {
            "title": "Titre",
            "scheduled_at": "Date et heure",
            "location": "Lieu",
            "online_url": "Lien visio",
            "status": "Statut",
            "quorum_required": "Quorum requis (%)",
        }
        widgets = {"scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class MFARequestForm(forms.Form):
    user = forms.ModelChoiceField(queryset=get_user_model().objects.all(), label="Utilisateur")
    channel = forms.ChoiceField(label="Canal", choices=(("email", "Email"), ("sms", "SMS")))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_SELECT if isinstance(field.widget, forms.Select) else BASE_INPUT)


class MFAVerifyForm(forms.Form):
    challenge = forms.ModelChoiceField(queryset=OTPChallenge.objects.select_related("user"), label="Challenge OTP")
    code = forms.CharField(label="Code OTP", min_length=6, max_length=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["challenge"].queryset = OTPChallenge.objects.filter(status=OTPChallenge.Status.PENDING).select_related("user")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_SELECT if isinstance(field.widget, forms.Select) else BASE_INPUT)


class ResolutionCreateForm(StyledModelForm):
    assembly = forms.ModelChoiceField(queryset=GeneralAssembly.all_objects.select_related("mutuelle"), label="Assemblée")

    class Meta:
        model = Resolution
        fields = ["assembly", "title", "description", "status", "approval_threshold", "closes_at"]
        labels = {
            "title": "Titre",
            "description": "Description",
            "status": "Statut",
            "approval_threshold": "Seuil d'approbation (%)",
            "closes_at": "Clôture du vote",
        }
        widgets = {"closes_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
