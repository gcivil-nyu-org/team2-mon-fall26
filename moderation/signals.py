"""Close open flags when an author deletes their own content (E03 #24).

Administrator removals resolve their flags first, so only still-open flags are
touched here. Without this, the moderation view would list items that no longer
exist.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete
from django.utils import timezone


def _withdraw_open_flags(sender, instance, **kwargs):
    from .models import ContentFlag

    ContentFlag.objects.filter(
        content_type=ContentType.objects.get_for_model(sender),
        object_id=instance.pk,
        status=ContentFlag.Status.OPEN,
    ).update(status=ContentFlag.Status.WITHDRAWN, resolved_at=timezone.now())


def connect(flaggable_types):
    for flaggable in flaggable_types:
        post_delete.connect(
            _withdraw_open_flags,
            sender=flaggable.model_label,
            dispatch_uid=f"moderation-withdraw-{flaggable.key}",
        )
