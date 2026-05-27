from django.contrib import admin

from accounts.models import LoginEvent, OTPChallenge, User, UserDevice


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "default_mutuelle", "mfa_enabled", "is_active", "failed_login_attempts")
    list_filter = ("role", "mfa_enabled", "is_active")
    search_fields = ("email", "phone", "first_name", "last_name")


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "device_id", "trusted", "last_ip", "last_seen_at")
    list_filter = ("trusted",)
    search_fields = ("user__email", "device_id", "name")


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "status", "attempts", "expires_at", "delivery_channel")
    list_filter = ("purpose", "status", "delivery_channel")
    search_fields = ("user__email", "delivery_target")


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("email", "user", "status", "ip_address", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "device_id", "user_agent")
