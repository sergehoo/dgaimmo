from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import BootstrapMutuelleView, LoginEventViewSet, RegisterView, UserDeviceViewSet, UserViewSet
from ai_engine.views import AIAnalysisViewSet
from claims.views import AssistanceClaimViewSet, ClaimDocumentViewSet
from contributions.views import ContributionPlanViewSet, ContributionViewSet
from governance.views import ElectronicSignatureViewSet, GeneralAssemblyViewSet, ResolutionViewSet, ResolutionVoteViewSet
from memberships.views import MemberViewSet
from mutuelles.views import MutuelleViewSet
from notifications.views import NotificationViewSet
from payments.views import PaymentViewSet
from real_estate.views import (
    BankPartnerViewSet,
    FinancingScenarioViewSet,
    MemberFinancialProfileViewSet,
    MortgageApplicationViewSet,
    PropertyLotViewSet,
    PropertyDocumentViewSet,
    PropertyReservationViewSet,
    QuotiteCessibleSimulationViewSet,
    RealEstateOpportunityViewSet,
    RealEstateProgramViewSet,
    RealEstateScoreViewSet,
)
from treasury.views import CashAccountViewSet, LedgerEntryViewSet
from core.views import healthz, readyz

admin.site.site_header = "MutuelleX"
admin.site.site_title = "MutuelleX Admin"
admin.site.index_title = "Pilotage mutualiste"

router = DefaultRouter()
router.register("users", UserViewSet)
router.register("security/devices", UserDeviceViewSet, basename="security-devices")
router.register("security/login-events", LoginEventViewSet, basename="security-login-events")
router.register("mutuelles", MutuelleViewSet)
router.register("members", MemberViewSet)
router.register("contribution-plans", ContributionPlanViewSet)
router.register("contributions", ContributionViewSet)
router.register("payments", PaymentViewSet)
router.register("claims/assistance", AssistanceClaimViewSet)
router.register("claims/documents", ClaimDocumentViewSet)
router.register("cash-accounts", CashAccountViewSet)
router.register("ledger-entries", LedgerEntryViewSet)
router.register("notifications", NotificationViewSet)
router.register("governance/assemblies", GeneralAssemblyViewSet)
router.register("governance/resolutions", ResolutionViewSet)
router.register("governance/votes", ResolutionVoteViewSet)
router.register("governance/signatures", ElectronicSignatureViewSet)
router.register("ai/analyses", AIAnalysisViewSet)
router.register("real-estate/programs", RealEstateProgramViewSet)
router.register("real-estate/opportunities", RealEstateOpportunityViewSet)
router.register("real-estate/lots", PropertyLotViewSet)
router.register("real-estate/documents", PropertyDocumentViewSet)
router.register("real-estate/reservations", PropertyReservationViewSet)
router.register("real-estate/quotite-simulations", QuotiteCessibleSimulationViewSet)
router.register("real-estate/member-financial-profiles", MemberFinancialProfileViewSet)
router.register("real-estate/financing-scenarios", FinancingScenarioViewSet)
router.register("real-estate/mortgage-applications", MortgageApplicationViewSet)
router.register("real-estate/bank-partners", BankPartnerViewSet)
router.register("real-estate/scores", RealEstateScoreViewSet, basename="real-estate-scores")

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/register/", RegisterView.as_view(), name="auth-register"),
    path("api/v1/auth/bootstrap-mutuelle/", BootstrapMutuelleView.as_view(), name="auth-bootstrap-mutuelle"),
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/v1/", include(router.urls)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("", include("dashboard.urls")),
]
