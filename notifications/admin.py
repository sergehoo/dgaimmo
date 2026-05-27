from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "channel", "status", "member", "recipient_user", "created_at")
    list_filter = ("channel", "status")
    search_fields = ("title", "body", "member__first_name", "member__last_name")
