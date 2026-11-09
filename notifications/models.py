"""E07 US27: in-app notifications (Inbox).

Agreed rules (see docs/E07-NOTIFICATIONS.md):

- Channel: in-app only (Inbox page and an unread count in the header).
- Timing: created as soon as the event happens, when the content becomes public.
- Followed-hotspot updates go to every follower except the person who acted, and can
  be switched off per type in ``NotificationPreference``. Routine updates (reviews,
  availability reports) are batched into one summary per hotspot while unread;
  availability alerts are sent individually. Moderation notices about a user's own
  content or flags are always sent.

Text is built from snapshot fields at display time, so a notification still reads
correctly after its review, discussion or hotspot is deleted or retired.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class Kind(models.TextChoices):
        FOLLOWED_REVIEW = "followed_review", "New reviews on a followed hotspot"
        FOLLOWED_AVAILABILITY = (
            "followed_availability",
            "New availability reports on a followed hotspot",
        )
        FOLLOWED_DISCUSSION = (
            "followed_discussion",
            "New discussion about a followed hotspot",
        )
        FOLLOWED_RETIRED = "followed_retired", "Followed hotspot removed"
        AVAILABILITY_ALERT = "availability_alert", "Followed hotspot may be down"
        AVAILABILITY_RECOVERED = (
            "availability_recovered",
            "Followed hotspot working again",
        )
        REVIEW_HELD = "review_held", "Review waiting for a moderator"
        REVIEW_HIDDEN = "review_hidden", "Review hidden after community flags"
        REVIEW_APPROVED = "review_approved", "Review approved"
        REVIEW_REMOVED = "review_removed", "Review removed by a moderator"
        FLAG_RESOLVED = "flag_resolved", "Flag reviewed"

    FOLLOWED_KINDS = {
        Kind.FOLLOWED_REVIEW,
        Kind.FOLLOWED_AVAILABILITY,
        Kind.FOLLOWED_DISCUSSION,
        Kind.FOLLOWED_RETIRED,
        Kind.AVAILABILITY_ALERT,
        Kind.AVAILABILITY_RECOVERED,
    }

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    hotspot = models.ForeignKey(
        "hotspots.Hotspot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # The review or discussion the notification opens, if any.
    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    # Snapshots used to build the text.
    hotspot_name = models.CharField(max_length=200, blank=True)
    actor_name = models.CharField(max_length=150, blank=True)
    detail = models.CharField(max_length=300, blank=True)
    count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        indexes = [
            models.Index(fields=["recipient", "read_at"], name="notification_unread"),
            models.Index(
                fields=["recipient", "kind", "content_type", "object_id"],
                name="notification_target",
            ),
        ]

    def __str__(self):
        return f"{self.kind} for {self.recipient_id}"

    @property
    def is_unread(self):
        return self.read_at is None

    @property
    def category(self):
        if self.kind == self.Kind.AVAILABILITY_ALERT:
            return "Availability alert"
        return "Followed hotspot" if self.kind in self.FOLLOWED_KINDS else "Moderation"

    @property
    def text(self):
        hotspot = self.hotspot_name or "a hotspot"
        kind = self.Kind
        if self.kind == kind.FOLLOWED_REVIEW:
            if self.count == 1:
                return f"1 new rating or review on {hotspot}. Select to view."
            return f"{self.count} new ratings and reviews on {hotspot}. Select to view."
        if self.kind == kind.FOLLOWED_AVAILABILITY:
            if self.count == 1:
                return f"{self.actor_name} reported {hotspot} as {self.detail.lower()}."
            return (
                f"{self.count} new availability reports on {hotspot}. "
                f"Latest: {self.detail.lower()}."
            )
        if self.kind == kind.AVAILABILITY_ALERT:
            return f"{hotspot} may be down: {self.detail}."
        if self.kind == kind.AVAILABILITY_RECOVERED:
            return f"{hotspot} looks to be working again: {self.detail}."
        if self.kind == kind.FOLLOWED_DISCUSSION:
            return f"{self.actor_name} started a discussion about {hotspot}: “{self.detail}”."
        if self.kind == kind.FOLLOWED_RETIRED:
            return (
                f"{hotspot} was removed from the public hotspot list. "
                "It no longer appears on the map or in your followed hotspots."
            )
        if self.kind == kind.REVIEW_HELD:
            return (
                f"Your review of {hotspot} is waiting for a moderator. "
                "Only you can see it until then."
            )
        if self.kind == kind.REVIEW_HIDDEN:
            return (
                f"Your review of {hotspot} was hidden after several community flags. "
                "A moderator will review it."
            )
        if self.kind == kind.REVIEW_APPROVED:
            return f"A moderator approved your review of {hotspot}. It is now public."
        if self.kind == kind.REVIEW_REMOVED:
            return (
                f"A moderator removed your review of {hotspot}. Reason: {self.detail}."
            )
        if self.kind == kind.FLAG_RESOLVED:
            outcome = "removed it" if self.detail == "removed" else "decided to keep it"
            return (
                f"A moderator reviewed the review you flagged on {hotspot} and {outcome}. "
                "Thanks for helping."
            )
        return self.get_kind_display()


class NotificationPreference(models.Model):
    """Per-user opt-outs for followed-hotspot updates. No row means everything is on."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    followed_reviews = models.BooleanField(
        "New ratings and reviews on hotspots I follow", default=True
    )
    followed_availability = models.BooleanField(
        "New availability reports on hotspots I follow", default=True
    )
    followed_availability_alerts = models.BooleanField(
        "Alerts when a hotspot I follow may be down, and when it recovers",
        default=True,
    )
    followed_discussions = models.BooleanField(
        "New discussions about hotspots I follow", default=True
    )

    def __str__(self):
        return f"Notification preferences for {self.user_id}"


class ReviewAnnouncement(models.Model):
    """Reviews already counted in followers' summaries, so each is counted once.

    A review can become public more than once (hidden by flags, then approved).
    """

    review = models.OneToOneField(
        "reviews.Review", on_delete=models.CASCADE, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)


class AvailabilityAlertState(models.Model):
    """Whether a hotspot is currently in the "may be down" state.

    Alerts fire on the change into that state and recovery notices on the change
    out of it, never on every report (see ``services.availability_reported``).
    """

    hotspot = models.OneToOneField(
        "hotspots.Hotspot", on_delete=models.CASCADE, related_name="+"
    )
    is_alerting = models.BooleanField(default=False)
    changed_at = models.DateTimeField(default=timezone.now)
