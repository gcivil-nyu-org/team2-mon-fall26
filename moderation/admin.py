from django.contrib import admin

from .models import ContentFlag, ModerationRecord


@admin.register(ContentFlag)
class ContentFlagAdmin(admin.ModelAdmin):
    list_display = ("content_type", "object_id", "flagged_by", "reason", "status", "created_at")
    list_filter = ("status", "reason", "content_type")
    readonly_fields = ("created_at", "resolved_at", "resolution")


@admin.register(ModerationRecord)
class ModerationRecordAdmin(admin.ModelAdmin):
    """The moderation log is append-only, including in Django admin."""

    list_display = ("created_at", "action", "content_label", "author_username", "reason", "moderator")
    list_filter = ("action", "reason", "content_label")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
