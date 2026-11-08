"""Create notifications for the agreed events (E07 US27).

Each function is called by the feature that owns the event, after the change is
saved: E03 reviews, E05 moderation, E06 availability reports, E08 discussions and
E04 hotspot retirement. See docs/E07-NOTIFICATIONS.md for the rules.
"""

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


def _review_detail(review):
    rating = f"{review.rating}/5"
    return f"{rating} and wrote a review" if review.body else rating


def review_published(review):
    """A rating or review became public on a hotspot (on save, or on approval).

    Edits never notify. A review that was already announced (for example, one that
    was hidden by flags and then approved) is not announced again.
    """
    hotspot = review.hotspot
    if review.is_demo or review.is_held or not hotspot.is_active:
        return 0
    recipients = set(
        _followers(hotspot, "followed_reviews", exclude_user_id=review.author_id)
    )
    if not recipients:
        return 0
    already = Notification.objects.filter(
        kind=Kind.FOLLOWED_REVIEW, **_target(review), recipient_id__in=recipients
    ).values_list("recipient_id", flat=True)
    return _create(
        recipients - set(already),
        Kind.FOLLOWED_REVIEW,
        hotspot,
        review,
        actor_name=review.author.username,
        detail=_review_detail(review),
    )


def availability_reported(report):
    """A Working/Unavailable report was submitted (E06).

    Reports are batched: while a follower has an unread availability notification for
    the hotspot, new reports update it ("3 new availability reports") instead of
    adding more.
    """
    hotspot = report.hotspot
    if not hotspot.is_active:
        return 0
    recipients = _followers(
        hotspot, "followed_availability", exclude_user_id=report.reporter_id
    )
    if not recipients:
        return 0
    status = report.get_status_display()
    unread = Notification.objects.filter(
        kind=Kind.FOLLOWED_AVAILABILITY,
        hotspot=hotspot,
        recipient_id__in=recipients,
        read_at__isnull=True,
    )
    batched = set(unread.values_list("recipient_id", flat=True))
    unread.update(
        count=F("count") + 1,
        detail=status,
        actor_name=report.reporter.username,
        updated_at=timezone.now(),
    )
    return len(batched) + _create(
        [pk for pk in recipients if pk not in batched],
        Kind.FOLLOWED_AVAILABILITY,
        hotspot,
        actor_name=report.reporter.username,
        detail=status,
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
    if kind == Kind.FOLLOWED_AVAILABILITY:
        return f"{hotspot.get_absolute_url()}#availability"
    if kind == Kind.REVIEW_REMOVED:
        return f"{hotspot.get_absolute_url()}#contribute"
    return f"{hotspot.get_absolute_url()}#reviews"
