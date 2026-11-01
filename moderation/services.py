from collections import Counter, defaultdict

from django.conf import settings
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


def open_flags_for(flaggable, pk):
    return flags_for(flaggable, pk).filter(status=ContentFlag.Status.OPEN)


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


# --- Automated holds ----------------------------------------------------------

def hold(flaggable, obj, reasons):
    """Hide an item until an administrator decides, recording why as an automated flag.

    ``reasons`` is a list of ``(Reason, detail)``. One open automated flag is kept
    per item; a later hold (for example after an edit) updates its details.
    """
    reason = reasons[0][0] if reasons else Reason.OTHER
    note = "; ".join(detail for _, detail in reasons)[:500]
    with transaction.atomic():
        flaggable.set_held(obj, True)
        existing = open_flags_for(flaggable, obj.pk).filter(flagged_by__isnull=True).first()
        if existing:
            existing.reason, existing.note = reason, note
            existing.save(update_fields=["reason", "note"])
        else:
            ContentFlag.objects.create(
                content_type=content_type_for(flaggable),
                object_id=obj.pk,
                flagged_by=None,
                reason=reason,
                note=note,
            )


def auto_hide_if_widely_flagged(flaggable, obj):
    """Community auto-hide: enough distinct users flagging a visible item hides it."""
    threshold = getattr(settings, "MODERATION_AUTO_HIDE_FLAGS", 3)
    user_flags = open_flags_for(flaggable, obj.pk).filter(flagged_by__isnull=False).count()
    if user_flags >= threshold and not flaggable.describe(obj)["is_held"]:
        flaggable.set_held(obj, True)
        return True
    return False


# --- Administrator queues -----------------------------------------------------

def held_count():
    return sum(flaggable.held_queryset().count() for flaggable in all_types())


def open_item_count():
    """Number of visible items with open flags (held items are counted separately)."""
    return len(flagged_items())


def _flag_details(flaggable, ids):
    reasons = defaultdict(Counter)
    notes = defaultdict(list)
    automated = defaultdict(list)
    latest = {}
    open_flags = ContentFlag.objects.filter(
        content_type=content_type_for(flaggable), object_id__in=list(ids), status=ContentFlag.Status.OPEN
    ).select_related("flagged_by").order_by("-created_at")
    for flag in open_flags:
        latest.setdefault(flag.object_id, flag.created_at)
        if flag.is_automated:
            automated[flag.object_id].extend(part for part in flag.note.split("; ") if part)
            continue
        reasons[flag.object_id][flag.get_reason_display()] += 1
        if flag.note and len(notes[flag.object_id]) < 3:
            notes[flag.object_id].append({"user": flag.flagged_by.username, "text": flag.note})
    return reasons, notes, automated, latest


def _item(flaggable, obj, reasons, notes, automated, latest):
    user_reasons = reasons[obj.pk]
    return {
        "type": flaggable,
        "pk": obj.pk,
        "key": f"{flaggable.key}:{obj.pk}|{flaggable.describe(obj)['version']}",
        "info": flaggable.describe(obj),
        "flag_count": sum(user_reasons.values()),
        "reasons": user_reasons.most_common(),
        "notes": notes[obj.pk],
        "automated": automated[obj.pk],
        "latest": latest.get(obj.pk),
    }


def held_items():
    """Items hidden by the automated checks or community auto-hide, newest first."""
    items = []
    for flaggable in all_types():
        objects = list(flaggable.held_queryset())
        details = _flag_details(flaggable, [obj.pk for obj in objects])
        items.extend(_item(flaggable, obj, *details) for obj in objects)
    items.sort(key=lambda item: item["latest"] or item["info"]["created_at"], reverse=True)
    return items


def flagged_items():
    """US19: visible items with open user flags, newest flag first."""
    items = []
    for flaggable in all_types():
        groups = (
            ContentFlag.objects.filter(
                content_type=content_type_for(flaggable),
                status=ContentFlag.Status.OPEN,
                flagged_by__isnull=False,
            )
            .values("object_id")
            .annotate(latest=Max("created_at"))
        )
        ids = [group["object_id"] for group in groups]
        if not ids:
            continue
        held_ids = set(flaggable.held_queryset().filter(pk__in=ids).values_list("pk", flat=True))
        objects = flaggable.admin_queryset().in_bulk([pk for pk in ids if pk not in held_ids])
        details = _flag_details(flaggable, objects.keys())
        items.extend(_item(flaggable, obj, *details) for obj in objects.values())
    items.sort(key=lambda item: item["latest"], reverse=True)
    return items


# --- Administrator decisions --------------------------------------------------

def _record(flaggable, obj, action, moderator, reason="", note="", new_status=None):
    info = flaggable.describe(obj)
    open_flags = open_flags_for(flaggable, obj.pk)
    record = ModerationRecord.objects.create(
        action=action,
        content_type=content_type_for(flaggable),
        object_id=obj.pk,
        content_label=flaggable.label,
        content_reference=info["reference"][:300],
        author_id=info["author_id"],
        author_username=info["author"],
        rating=info.get("rating"),
        content_text=info["text"],
        reason=reason,
        note=note,
        flag_count=open_flags.filter(flagged_by__isnull=False).count(),
        moderator=moderator,
    )
    open_flags.update(status=new_status, resolved_at=timezone.now(), resolution=record)
    return record


def _lock(flaggable, obj):
    """Re-read the item under a row lock, so decisions and author edits serialize.

    Returns None when the item no longer exists (for example, the author deleted it).
    """
    return flaggable.admin_queryset().select_for_update().filter(pk=obj.pk).first()


def remove_content(flaggable, obj, moderator, reason, note=""):
    """US20: log the decision, close the item's flags, then delete the item.

    Deleting a review removes it from every public page and its rating from the
    hotspot's average, exactly as when an author deletes their own review.
    Returns None, and changes nothing, when the item is already gone.
    """
    if reason not in Reason.values:
        raise ValueError("A moderation reason is required.")
    with transaction.atomic():
        obj = _lock(flaggable, obj)
        if obj is None:
            return None
        record = _record(
            flaggable, obj, ModerationRecord.Action.REMOVED, moderator, reason, note,
            ContentFlag.Status.REMOVED,
        )
        obj.delete()
    return record


def dismiss_flags(flaggable, obj, moderator):
    """Close an item's open flags without changing the content."""
    with transaction.atomic():
        obj = _lock(flaggable, obj)
        if obj is None:
            return None
        return _record(
            flaggable, obj, ModerationRecord.Action.DISMISSED, moderator,
            new_status=ContentFlag.Status.DISMISSED,
        )


def approve(flaggable, obj, moderator, version=None):
    """Publish a held item and close its flags.

    ``version`` is the item's version when the administrator looked at it. If the
    author edited it since, nothing is published: the administrator must review
    the new text first. Returns None when nothing was approved.
    """
    with transaction.atomic():
        obj = _lock(flaggable, obj)
        if obj is None or not flaggable.describe(obj)["is_held"]:
            return None
        if version is not None and flaggable.describe(obj)["version"] != version:
            return None
        record = _record(
            flaggable, obj, ModerationRecord.Action.APPROVED, moderator,
            new_status=ContentFlag.Status.DISMISSED,
        )
        flaggable.set_held(obj, False)
    return record
