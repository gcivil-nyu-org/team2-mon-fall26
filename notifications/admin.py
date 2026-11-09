from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "kind", "hotspot_name", "read_at")
    list_filter = ("kind",)
    readonly_fields = ("created_at", "updated_at")


admin.site.register(NotificationPreference)
