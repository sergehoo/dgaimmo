from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import LoginEvent, OTPChallenge, User, UserDevice
from core.models import TenantQuota
from mutuelles.models import Mutuelle, MutuelleMembership


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "role",
            "default_mutuelle",
            "mfa_enabled",
            "is_active",
        ]
        read_only_fields = ["id", "is_active"]


class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = ["id", "user", "device_id", "name", "trusted", "last_ip", "last_seen_at"]
        read_only_fields = ["id", "user", "device_id", "last_ip", "last_seen_at"]


class OTPChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTPChallenge
        fields = ["id", "purpose", "status", "attempts", "expires_at", "delivery_channel", "delivery_target", "created_at"]
        read_only_fields = fields


class LoginEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginEvent
        fields = ["id", "user", "email", "status", "ip_address", "user_agent", "device_id", "metadata", "created_at"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            phone=validated_data.get("phone") or None,
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            role=User.Role.MEMBER,
        )
        return user


class BootstrapMutuelleSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    mutuelle_name = serializers.CharField(max_length=180)
    country = serializers.CharField(max_length=2, default="CI")
    currency = serializers.CharField(max_length=3, default="XOF")

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value

    def validate_mutuelle_name(self, value):
        base_slug = slugify(value)
        if Mutuelle.objects.filter(slug=base_slug).exists():
            raise serializers.ValidationError("Une mutuelle existe déjà avec ce nom.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        mutuelle = Mutuelle.objects.create(
            name=validated_data["mutuelle_name"],
            slug=slugify(validated_data["mutuelle_name"]),
            country=validated_data.get("country", "CI").upper(),
            currency=validated_data.get("currency", "XOF").upper(),
            status=Mutuelle.Status.ACTIVE,
        )
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            phone=validated_data.get("phone") or None,
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            role=User.Role.MUTUELLE_ADMIN,
            default_mutuelle=mutuelle,
        )
        MutuelleMembership.objects.create(mutuelle=mutuelle, user=user, role=User.Role.MUTUELLE_ADMIN, permissions=["*"])
        TenantQuota.objects.create(mutuelle=mutuelle)
        refresh = RefreshToken.for_user(user)
        return {
            "user": user,
            "mutuelle": mutuelle,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
