"""E05: the community content types that can be flagged and moderated.

One shared reporting and moderation workflow serves every kind of community
content (US19-US21). Each kind is registered here once. E03 hotspot reviews are
registered today; when E08 adds forum posts, comments and replies, each one is a
new ``FlaggableType`` entry and the flag form, moderation view and removal flow
work for it unchanged.
"""
from dataclasses import dataclass
from typing import Callable

from django.apps import apps
from django.http import Http404


@dataclass(frozen=True)
class FlaggableType:
    key: str
    """URL slug, e.g. ``review``."""
    label: str
    """Content type shown to administrators, e.g. ``Hotspot review``."""
    model_label: str
    """``app_label.ModelName`` of the content model."""
    public_queryset: Callable
    """Items a contributor can currently see and flag."""
    describe: Callable
    """Returns a dict describing one item for administrators (see ``_describe_review``)."""
    affects_rating: bool = False

    @property
    def model(self):
        return apps.get_model(self.model_label)

    def admin_queryset(self):
        return self.model._default_manager.all()


def _public_reviews():
    from reviews.services import visible_reviews

    # Only written reviews are shown individually, so only they can be flagged.
    return visible_reviews().exclude(body="").filter(hotspot__is_active=True)


def _describe_review(review):
    hotspot = review.hotspot
    return {
        "author": review.author.username,
        "author_id": review.author_id,
        "text": review.body,
        "rating": review.rating,
        "reference": f"{hotspot.display_name} (NYC ID {hotspot.pk})",
        "url": f"{hotspot.get_absolute_url()}#review-{review.pk}" if hotspot.is_active else "",
        "created_at": review.created_at,
        "is_demo": review.is_demo,
        "is_public": hotspot.is_active,
    }


REVIEW = FlaggableType(
    key="review",
    label="Hotspot review",
    model_label="reviews.Review",
    public_queryset=_public_reviews,
    describe=_describe_review,
    affects_rating=True,
)

# E08: add forum post, comment and reply types here.
_TYPES = {REVIEW.key: REVIEW}


def all_types():
    return list(_TYPES.values())


def get_type(key):
    try:
        return _TYPES[key]
    except KeyError:
        raise Http404("Unknown content type.") from None


def type_for_model(model):
    label = model._meta.label
    for flaggable in _TYPES.values():
        if flaggable.model_label == label:
            return flaggable
    return None
