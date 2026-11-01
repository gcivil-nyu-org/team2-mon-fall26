from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Reason(models.TextChoices):
    """Shared reasons for flags (US21) and administrator removals (US20).

    Proposed policy; the exact list is for the team to agree (#30).
    """

    SPAM = "spam", "Spam or advertising"
    OFFENSIVE = "offensive", "Harassment, hate or offensive language"
    MISLEADING = "misleading", "False or misleading information"
    OFF_TOPIC = "off_topic", "Not about this hotspot or its Wi-Fi"
    PERSONAL_INFO = "personal_info", "Shares someone's personal information"
    OTHER = "other", "Something else"


class ContentFlag(models.Model):
    """US21: one contributor's report that a piece of community content is inappropriate.

    The flagged item is a generic reference (content type + id), so E03 reviews and
    E08 forum content share this one table.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REMOVED = "removed", "Content removed"
        DISMISSED = "dismissed", "Dismissed"
        WITHDRAWN = "withdrawn", "Deleted by its author"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    flagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_flags"
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.ForeignKey(
        "ModerationRecord", null=True, blank=True, on_delete=models.SET_NULL, related_name="flags"
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "flagged_by"],
                name="one_flag_per_user_per_item",
            )
        ]
        indexes = [models.Index(fields=["status", "content_type", "object_id"])]

    def __str__(self):
        return f"{self.get_reason_display()} flag on {self.content_type.model} {self.object_id}"


class ModerationRecord(models.Model):
    """US20: permanent log of an administrator's moderation decision.

    A snapshot is kept because removed content is deleted from the public tables.
    Administrators never edit the author's words.
    """

    class Action(models.TextChoices):
        REMOVED = "removed", "Removed"
        DISMISSED = "dismissed", "Flags dismissed"

    action = models.CharField(max_length=12, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_label = models.CharField(max_length=60)
    content_reference = models.CharField(max_length=300)
    author_username = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    content_text = models.TextField(blank=True)
    reason = models.CharField(max_length=20, choices=Reason.choices, blank=True)
    note = models.CharField(max_length=500, blank=True)
    flag_count = models.PositiveIntegerField(default=0)
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.get_action_display()}: {self.content_label} {self.object_id}"
