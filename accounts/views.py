from rest_framework import decorators, generics, permissions, response, status, viewsets

from accounts.models import LoginEvent, OTPChallenge, User, UserDevice
from accounts.serializers import BootstrapMutuelleSerializer, LoginEventSerializer, OTPChallengeSerializer, RegisterSerializer, UserDeviceSerializer, UserSerializer
from accounts.services import create_otp_challenge, verify_otp_challenge
from core.permissions import IsMutuelleAdmin


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsMutuelleAdmin]
    search_fields = ["email", "phone", "first_name", "last_name"]
    ordering_fields = ["date_joined", "email"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        if self.request.user.is_superuser:
            return User.objects.all()
        return User.objects.filter(default_mutuelle=getattr(self.request, "mutuelle", None))

    @decorators.action(detail=False, methods=["post"], url_path="mfa/request")
    def mfa_request(self, request):
        challenge, code = create_otp_challenge(request.user)
        return response.Response({**OTPChallengeSerializer(challenge).data, "dev_code": code}, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=["post"], url_path="mfa/verify")
    def mfa_verify(self, request):
        challenge = OTPChallenge.objects.get(id=request.data["challenge"])
        verified = verify_otp_challenge(challenge, request.data["code"])
        if verified:
            request.user.mfa_enabled = True
            request.user.save(update_fields=["mfa_enabled"])
        return response.Response({"verified": verified, "status": challenge.status})


class UserDeviceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserDevice.objects.none()
    serializer_class = UserDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserDevice.objects.none()
        return UserDevice.objects.filter(user=self.request.user).order_by("-last_seen_at")


class LoginEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LoginEvent.objects.none()
    serializer_class = LoginEventSerializer
    permission_classes = [IsMutuelleAdmin]
    filterset_fields = ["status", "email"]
    search_fields = ["email", "device_id", "user_agent"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LoginEvent.objects.none()
        if self.request.user.is_superuser:
            return LoginEvent.objects.select_related("user")
        return LoginEvent.objects.filter(user__default_mutuelle=getattr(self.request, "mutuelle", None)).select_related("user")


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class BootstrapMutuelleView(generics.CreateAPIView):
    serializer_class = BootstrapMutuelleSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return response.Response(
            {
                "user": UserSerializer(payload["user"]).data,
                "mutuelle": {
                    "id": payload["mutuelle"].id,
                    "name": payload["mutuelle"].name,
                    "slug": payload["mutuelle"].slug,
                    "country": payload["mutuelle"].country,
                    "currency": payload["mutuelle"].currency,
                },
                "access": payload["access"],
                "refresh": payload["refresh"],
            },
            status=status.HTTP_201_CREATED,
        )
