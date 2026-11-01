from collections import Counter, defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from .models import ContentFlag, ModerationRecord, Reason
from .registry import all_types


def content_type_for(flaggable):
    return ContentType.objects.get_for_model(flaggable.model)


def flags_for(flaggable, pk):
    return ContentFlag.objects.filter(content_type=content_type_for(flaggable), object_id=pk)


def flagged_ids(user, flaggable):
    """Ids of items of this type the user has already flagged (any status)."""
    if not user.is_authenticated:
        return set()
    return set(
        ContentFlag.objects.filter(
            flagged_by=user, content_type=content_type_for(flaggable)
        ).values_list("object_id", flat=True)
    )


def open_flag_counts(flaggable, ids):
    rows = (
        ContentFlag.objects.filter(
            content_type=content_type_for(flaggable),
            object_id__in=list(ids),
            status=ContentFlag.Status.OPEN,
        )
        .values("object_id")
        .annotate(total=Count("pk"))
    )
    return {row["object_id"]: row["total"] for row in rows}


def open_item_count():
    """Number of distinct items with at least one open flag."""
    return (
        ContentFlag.objects.filter(status=ContentFlag.Status.OPEN)
        .values("content_type", "object_id")
        .distinct()
        .count()
    )


def flagged_items():
    """US19: every item with open flags, newest flag first, across all content types."""
    items = []
    for flaggable in all_types():
        open_flags = ContentFlag.objects.filter(
            content_type=content_type_for(flaggable), status=ContentFlag.Status.OPEN
        )
        groups = (
            open_flags.values("object_id")
            .annotate(total=Count("pk"), latest=Max("created_at"))
        )
        if not groups:
            continue
        ids = [group["object_id"] for group in groups]
        objects = flaggable.admin_queryset().in_bulk(ids)
        reasons = defaultdict(Counter)
        notes = defaultdict(list)
        for flag in open_flags.select_related("flagged_by").order_by("-created_at"):
            reasons[flag.object_id][flag.get_reason_display()] += 1
            if flag.note and len(notes[flag.object_id]) < 3:
                notes[flag.object_id].append({"user": flag.flagged_by.username, "text": flag.note})
        for group in groups:
            obj = objects.get(group["object_id"])
            if obj is None:
                continue
            items.append({
                "type": flaggable,
                "pk": obj.pk,
                "info": flaggable.describe(obj),
                "flag_count": group["total"],
                "latest": group["latest"],
                "reasons": reasons[obj.pk].most_common(),
                "notes": notes[obj.pk],
            })
    items.sort(key=lambda item: item["latest"], reverse=True)
    return items


def _record(flaggable, obj, action, moderator, reason="", note=""):
    info = flaggable.describe(obj)
    open_flags = flags_for(flaggable, obj.pk).filter(status=ContentFlag.Status.OPEN)
    record = ModerationRecord.objects.create(
        action=action,
        content_type=content_type_for(flaggable),
        object_id=obj.pk,
        content_label=flaggable.label,
        content_reference=info["reference"][:300],
        author_username=info["author"],
        rating=info.get("rating"),
        content_text=info["text"],
        reason=reason,
        note=note,
        flag_count=open_flags.count(),
        moderator=moderator,
    )
    status = (
        ContentFlag.Status.REMOVED
        if action == ModerationRecord.Action.REMOVED
        else ContentFlag.Status.DISMISSED
    )
    open_flags.update(status=status, resolved_at=timezone.now(), resolution=record)
    return record


def remove_content(flaggable, obj, moderator, reason, note=""):
    """US20: log the decision, close the item's flags, then delete the item.

    Deleting a review removes it from every public page and its rating from the
    hotspot's average, exactly as when an author deletes their own review.
    """
    if reason not in Reason.values:
        raise ValueError("A moderation reason is required.")
    with transaction.atomic():
        record = _record(flaggable, obj, ModerationRecord.Action.REMOVED, moderator, reason, note)
        obj.delete()
    return record


def dismiss_flags(flaggable, obj, moderator):
    """Close an item's open flags without changing the content."""
    with transaction.atomic():
        return _record(flaggable, obj, ModerationRecord.Action.DISMISSED, moderator)
