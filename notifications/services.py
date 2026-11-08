"""Create notifications for the agreed events (E07 US27).

Each function is called by the feature that owns the event, after the change is
saved: E03 reviews, E05 moderation, E06 availability reports, E08 discussions and
E04 hotspot retirement. See docs/E07-NOTIFICATIONS.md for the rules.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from .models import Notification

Kind = Notification.Kind


def _followers(hotspot, preference=None, exclude_user_id=None):
    """Ids of users following ``hotspot`` who have not switched ``preference`` off."""
    from hotspots.models import HotspotFollow

    follows = HotspotFollow.objects.filter(hotspot=hotspot, user__is_active=True)
    if exclude_user_id is not None:
        follows = follows.exclude(user_id=exclude_user_id)
    if preference:
        follows = follows.exclude(
            **{f"user__notification_preference__{preference}": False}
        )
    return list(follows.values_list("user_id", flat=True))


def _target(obj):
    if obj is None:
        return {}
    return {
        "content_type": ContentType.objects.get_for_model(type(obj)),
        "object_id": obj.pk,
    }


def _create(recipient_ids, kind, hotspot=None, obj=None, **fields):
    now = timezone.now()
    rows = [
        Notification(
            recipient_id=recipient_id,
            kind=kind,
            hotspot=hotspot,
            hotspot_name=hotspot.display_name if hotspot else "",
            created_at=now,
            updated_at=now,
            **_target(obj),
            **fields,
        )
        for recipient_id in dict.fromkeys(recipient_ids)
    ]
    Notification.objects.bulk_create(rows)
    return len(rows)


# --- Followed hotspots (E07) ----------------------------------------------------


def _batch(recipients, kind, hotspot, **fields):
    """Fold one more event into each follower's unread summary for this hotspot.

    Followers with an unread notification of this kind for the hotspot get its
    count increased and moved to the top; everyone else gets a new one. Once read,
    the next event starts a new summary.
    """
    unread = Notification.objects.filter(
        kind=kind, hotspot=hotspot, recipient_id__in=recipients, read_at__isnull=True
    )
    batched = set(unread.values_list("recipient_id", flat=True))
    unread.update(count=F("count") + 1, updated_at=timezone.now(), **fields)
    return len(batched) + _create(
        [pk for pk in recipients if pk not in batched], kind, hotspot, **fields
    )


def review_published(review):
    """A rating or review became public on a hotspot (on save, or on approval).

    Followers get one summary per hotspot ("3 new ratings and reviews on ..."), not
    one notification per review. Edits never count. Each review is counted once,
    even if it is later hidden by flags and approved again.
    """
    from .models import ReviewAnnouncement

    hotspot = review.hotspot
    if review.is_demo or review.is_held or not hotspot.is_active:
        return 0
    _, created = ReviewAnnouncement.objects.get_or_create(review=review)
    if not created:
        return 0
    recipients = _followers(
        hotspot, "followed_reviews", exclude_user_id=review.author_id
    )
    return _batch(recipients, Kind.FOLLOWED_REVIEW, hotspot) if recipients else 0


def availability_reported(report):
    """A Working/Unavailable report was submitted (E06).

    Two separate things happen:

    - Routine updates: reports are batched into one unread summary per hotspot
      ("3 new availability reports ... Latest: unavailable").
    - Alerts: when the hotspot enters the "may be down" state (see
      ``_alert_condition``) followers get an individual alert, and when it
      recovers, a "working again" notice. Alerts fire only on those changes of
      state, never on every report.
    """
    hotspot = report.hotspot
    if not hotspot.is_active:
        return 0
    count = _update_alert_state(hotspot, report.reporter_id)
    recipients = _followers(
        hotspot, "followed_availability", exclude_user_id=report.reporter_id
    )
    if recipients:
        count += _batch(
            recipients,
            Kind.FOLLOWED_AVAILABILITY,
            hotspot,
            detail=report.get_status_display(),
            actor_name=report.reporter.username,
        )
    return count


# Alert thresholds. Like the E06 reliability rules, they are proposals for the team
# and can be tuned in settings. The gap between ALERT_BELOW and RECOVER_AT stops a
# hotspot from flapping between "down" and "working again" on every report.
def _alert_setting(name, default):
    return getattr(settings, name, default)


def _alert_condition(hotspot):
    """Return ``(is_down, is_recovered, detail)`` for the hotspot's current reports.

    Down when either:
    - a burst: at least AVAILABILITY_ALERT_UNAVAILABLE_REPORTS different people's
      latest reports in the last AVAILABILITY_ALERT_WINDOW_HOURS say Unavailable; or
    - the reliability score (E06 US23: 30 days, newest report per person, at least
      3 people) is below AVAILABILITY_ALERT_BELOW percent.

    Recovered when there is no burst and the score is at least
    AVAILABILITY_RECOVER_AT percent.
    """
    from availability.models import AvailabilityReport
    from availability.services import hotspot_availability, hotspot_reports

    score = hotspot_availability(hotspot)["score"]
    hours = _alert_setting("AVAILABILITY_ALERT_WINDOW_HOURS", 24)
    window = timezone.now() - timedelta(hours=hours)
    recent_unavailable = sum(
        1
        for report in hotspot_reports(hotspot)
        if report.status == AvailabilityReport.Status.UNAVAILABLE
        and report.created_at >= window
    )
    burst = recent_unavailable >= _alert_setting(
        "AVAILABILITY_ALERT_UNAVAILABLE_REPORTS", 3
    )
    low = score is not None and score < _alert_setting("AVAILABILITY_ALERT_BELOW", 50)
    if burst:
        detail = (
            f"{recent_unavailable} people reported it unavailable "
            f"in the last {hours} hours"
        )
    elif low:
        detail = f"its reliability score dropped to {score}%"
    else:
        detail = f"its reliability score is back to {score}%"
    recovered = (
        not burst
        and score is not None
        and score >= _alert_setting("AVAILABILITY_RECOVER_AT", 70)
    )
    return burst or low, recovered, detail


def _update_alert_state(hotspot, actor_id):
    from .models import AvailabilityAlertState

    state, _ = AvailabilityAlertState.objects.get_or_create(hotspot=hotspot)
    is_down, recovered, detail = _alert_condition(hotspot)
    if not state.is_alerting and is_down:
        state.is_alerting, kind = True, Kind.AVAILABILITY_ALERT
    elif state.is_alerting and recovered:
        state.is_alerting, kind = False, Kind.AVAILABILITY_RECOVERED
    else:
        return 0
    state.changed_at = timezone.now()
    state.save(update_fields=["is_alerting", "changed_at"])
    return _create(
        _followers(hotspot, "followed_availability_alerts", exclude_user_id=actor_id),
        kind,
        hotspot,
        detail=detail,
    )


def discussion_started(post):
    """A forum topic linked to a hotspot was created (E08)."""
    hotspot = post.hotspot
    if hotspot is None or not hotspot.is_active:
        return 0
    return _create(
        _followers(hotspot, "followed_discussions", exclude_user_id=post.author_id),
        Kind.FOLLOWED_DISCUSSION,
        hotspot,
        post,
        actor_name=post.author.username,
        detail=post.title[:300],
    )


def hotspot_retired(hotspot):
    """An administrator removed a hotspot from public discovery (E04). Always sent."""
    return _create(_followers(hotspot), Kind.FOLLOWED_RETIRED, hotspot)


# --- Moderation (E05) -------------------------------------------------------------


def _author_notice(kind, obj, info, **fields):
    author_id = info.get("author_id")
    if not author_id or info.get("is_demo"):
        return 0
    return _create([author_id], kind, getattr(obj, "hotspot", None), obj, **fields)


def content_held(info, obj):
    """The automated checks held the author's content for a moderator."""
    return _author_notice(Kind.REVIEW_HELD, obj, info)


def content_hidden(info, obj):
    """Enough community flags hid the author's content until a moderator decides."""
    return _author_notice(Kind.REVIEW_HIDDEN, obj, info)


def content_approved(info, obj, flagger_ids):
    """A moderator published held content. Followers hear about it now, if not before."""
    count = _author_notice(Kind.REVIEW_APPROVED, obj, info)
    count += flags_resolved(flagger_ids, obj, removed=False)
    from reviews.models import Review

    if isinstance(obj, Review):
        count += review_published(obj)
    return count


def content_removed(info, obj, reason_label, flagger_ids):
    """A moderator removed content. The author learns the reason, never who flagged it.

    No content link is stored: the item is deleted, so the notice opens its hotspot.
    """
    hotspot = getattr(obj, "hotspot", None)
    count = 0
    if info.get("author_id") and not info.get("is_demo"):
        count += _create(
            [info["author_id"]], Kind.REVIEW_REMOVED, hotspot, detail=reason_label
        )
    count += _create(
        [pk for pk in flagger_ids if pk != info.get("author_id")],
        Kind.FLAG_RESOLVED,
        hotspot,
        detail="removed",
    )
    return count


def flags_resolved(flagger_ids, obj, removed):
    """Tell the people who flagged an item that a moderator made a decision."""
    return _create(
        flagger_ids,
        Kind.FLAG_RESOLVED,
        getattr(obj, "hotspot", None),
        obj,
        detail="removed" if removed else "kept",
    )


# --- Reading ----------------------------------------------------------------------


def unread_count(user):
    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_read(queryset):
    return queryset.filter(read_at__isnull=True).update(read_at=timezone.now())


def _review_url(notification):
    from reviews.models import Review

    review = (
        Review.objects.select_related("hotspot")
        .filter(pk=notification.object_id, hotspot__is_active=True)
        .first()
    )
    if review is None:
        return None
    base = review.hotspot.get_absolute_url()
    if review.author_id == notification.recipient_id:
        # Authors see their own review (held or not) in the contribution panel.
        return f"{base}#contribute"
    if review.is_held:
        return None
    return f"{base}#review-{review.pk}" if review.body else f"{base}#reviews"


def target_url(notification):
    """Where selecting the notification goes, or None if that content is gone."""
    kind = notification.kind
    hotspot = notification.hotspot
    if kind == Kind.FOLLOWED_RETIRED:
        return reverse("hotspots:followed")
    if kind == Kind.FOLLOWED_DISCUSSION:
        from forum.models import ForumPost

        post = ForumPost.objects.filter(pk=notification.object_id).first()
        return post.get_absolute_url() if post else None
    if notification.object_id and notification.content_type.model == "review":
        url = _review_url(notification)
        if url or kind != Kind.FLAG_RESOLVED:
            return url
    if hotspot is None or not hotspot.is_active:
        return None
    if kind in (
        Kind.FOLLOWED_AVAILABILITY,
        Kind.AVAILABILITY_ALERT,
        Kind.AVAILABILITY_RECOVERED,
    ):
        return f"{hotspot.get_absolute_url()}#availability"
    if kind == Kind.REVIEW_REMOVED:
        return f"{hotspot.get_absolute_url()}#contribute"
    return f"{hotspot.get_absolute_url()}#reviews"
