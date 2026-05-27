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
from memberships.models import Member
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


class StyledModelForm(forms.ModelForm):
    def _style_fields(self):
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", BASE_TEXTAREA)
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", BASE_SELECT)
            elif isinstance(field.widget, forms.ColorInput) or name in {"primary_color", "accent_color"}:
                field.widget = forms.ColorInput(attrs={**field.widget.attrs, "class": COLOR_INPUT})
            else:
                field.widget.attrs.setdefault("class", BASE_INPUT)


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
    class Meta:
        model = Mutuelle
        fields = ["name", "legal_name", "country", "currency", "primary_color", "accent_color"]
        labels = {
            "name": "Nom de la mutuelle",
            "legal_name": "Raison sociale",
            "country": "Pays",
            "currency": "Devise",
            "primary_color": "Couleur principale",
            "accent_color": "Couleur secondaire",
        }
        widgets = {
            "primary_color": forms.ColorInput,
            "accent_color": forms.ColorInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def save(self, commit=True):
        instance = super().save(commit=False)
        base_slug = slugify(instance.name)
        slug = base_slug
        index = 2
        while Mutuelle.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{index}"
            index += 1
        instance.slug = slug
        instance.status = Mutuelle.Status.ACTIVE
        if commit:
            instance.save()
        return instance


class PublicMutuelleSignupForm(forms.Form):
    mutuelle_name = forms.CharField(label="Nom de la mutuelle", max_length=180)
    legal_name = forms.CharField(label="Raison sociale", max_length=180, required=False)
    country = forms.CharField(label="Pays", max_length=2, initial="CI")
    currency = forms.CharField(label="Devise", max_length=3, initial="XOF")
    primary_color = forms.CharField(
        label="Couleur principale",
        max_length=16,
        initial="#003b98",
        widget=forms.ColorInput(attrs={"class": COLOR_INPUT}),
    )
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Email professionnel")
    phone = forms.CharField(label="Téléphone", max_length=32, required=False)
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "primary_color":
                continue
            field.widget.attrs.setdefault("class", BASE_INPUT)
        self.fields["country"].widget.attrs.setdefault("maxlength", "2")
        self.fields["currency"].widget.attrs.setdefault("maxlength", "3")

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

    def clean_mutuelle_name(self):
        name = self.cleaned_data["mutuelle_name"].strip()
        base_slug = slugify(name)
        if not base_slug:
            raise forms.ValidationError("Le nom doit contenir au moins une lettre ou un chiffre.")
        if Mutuelle.objects.filter(slug=base_slug).exists():
            raise forms.ValidationError("Une mutuelle avec ce nom existe déjà. Ajoutez une précision au nom.")
        return name

    def clean_country(self):
        return self.cleaned_data["country"].strip().upper()

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().upper()

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
            legal_name=data.get("legal_name", ""),
            slug=slugify(data["mutuelle_name"]),
            country=data["country"],
            currency=data["currency"],
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
            "primary_color": forms.ColorInput,
            "accent_color": forms.ColorInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class MemberCreateForm(StyledModelForm):
    mutuelle = forms.ModelChoiceField(queryset=Mutuelle.objects.all(), label="Mutuelle")

    class Meta:
        model = Member
        fields = ["mutuelle", "member_code", "first_name", "last_name", "phone", "email", "status", "kyc_validated"]
        labels = {
            "member_code": "Code membre",
            "first_name": "Prénom",
            "last_name": "Nom",
            "phone": "Téléphone",
            "email": "Email",
            "status": "Statut",
            "kyc_validated": "KYC validé",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["member_code"].required = False
        self.fields["member_code"].help_text = "Laissez vide pour générer un code automatiquement."
        self._style_fields()

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
        instance.member_code = (instance.member_code or "").strip().upper()
        if not instance.member_code:
            instance.member_code = self._generate_member_code(instance.mutuelle)
        instance.qr_token = f"qr-{instance.member_code.lower()}-{uuid.uuid4().hex[:8]}"
        instance.joined_at = timezone.now().date()
        if commit:
            instance.save()
        return instance


class FinancialProfileForm(StyledModelForm):
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre")

    class Meta:
        model = MemberFinancialProfile
        fields = [
            "member",
            "net_monthly_salary",
            "complementary_income",
            "fixed_charges",
            "pensions",
            "mutual_contributions",
            "dependents_count",
            "professional_seniority_months",
            "contract_type",
            "employment_type",
            "risk_level",
        ]
        labels = {
            "net_monthly_salary": "Salaire net mensuel",
            "complementary_income": "Revenus complémentaires",
            "fixed_charges": "Charges fixes",
            "pensions": "Pensions",
            "mutual_contributions": "Cotisations mutuelle",
            "dependents_count": "Personnes à charge",
            "professional_seniority_months": "Ancienneté professionnelle (mois)",
            "contract_type": "Type de contrat",
            "employment_type": "Statut professionnel",
            "risk_level": "Niveau de risque",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["member"].queryset = Member.all_objects.filter(financial_profile__isnull=True).select_related("mutuelle")
        self._style_fields()


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
    member = forms.ModelChoiceField(queryset=Member.all_objects.select_related("mutuelle"), label="Membre")
    requested_amount = forms.DecimalField(label="Montant demandé", max_digits=14, decimal_places=2)
    requested_duration_months = forms.IntegerField(label="Période d'amortissement (mois)", min_value=1, initial=120)
    annual_interest_rate = forms.DecimalField(label="Taux annuel (%)", max_digits=5, decimal_places=2, initial=7)
    max_debt_ratio = forms.DecimalField(label="Taux d'endettement max (%)", max_digits=5, decimal_places=2, initial=33)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_SELECT if isinstance(field.widget, forms.Select) else BASE_INPUT)


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
