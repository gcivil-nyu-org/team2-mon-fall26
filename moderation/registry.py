"""E05: the community content types that can be flagged and moderated.

One shared reporting and moderation workflow serves every kind of community
content (US19-US21). Each kind is registered here once: E03 hotspot reviews and
E08 discussion posts and comments (replies are comments with a parent). The flag
form, moderation queue, removal flow and notifications work the same for each.
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
    set_held: Callable = None
    """``set_held(obj, held)`` hides or publishes the item (E05 hold-for-review)."""
    held_queryset: Callable = None
    """Items currently hidden while they wait for an administrator."""
    affects_rating: bool = False
    removal_effect: Callable = None
    """Optional ``removal_effect(obj)`` sentence about what else removal deletes."""

    @property
    def model(self):
        return apps.get_model(self.model_label)

    def admin_queryset(self):
        return self.model._default_manager.all()


def _public_reviews():
    from reviews.services import visible_reviews

    return visible_reviews().filter(hotspot__is_active=True)


def _describe_review(review):
    hotspot = review.hotspot
    return {
        "author": review.author.username,
        "author_id": review.author_id,
        "text": review.body,
        "rating": review.rating,
        "reference": f"{hotspot.display_name} (NYC ID {hotspot.pk})",
        "url": (
            f"{hotspot.get_absolute_url()}#review-{review.pk}"
            if hotspot.is_active and not review.is_held
            else ""
        ),
        "created_at": review.created_at,
        "is_demo": review.is_demo,
        "is_held": review.is_held,
        "is_public": hotspot.is_active and not review.is_held,
        # Changes whenever the author edits; approvals check it (see services.approve).
        "version": review.updated_at.isoformat(),
    }


def _held_reviews():
    from reviews.models import Review

    return Review.objects.filter(is_held=True)


def _set_review_held(review, held):
    from reviews.models import Review

    Review.objects.filter(pk=review.pk).update(is_held=held)
    review.is_held = held


def _review_removal_effect(review):
    count = review.replies.count()
    if not count:
        return ""
    return f"This also removes {count} {'reply' if count == 1 else 'replies'}."


REVIEW = FlaggableType(
    key="review",
    label="Hotspot review",
    model_label="reviews.Review",
    public_queryset=_public_reviews,
    describe=_describe_review,
    set_held=_set_review_held,
    held_queryset=_held_reviews,
    affects_rating=True,
    removal_effect=_review_removal_effect,
)


# --- Replies to hotspot reviews ----------------------------------------------


def _public_review_replies():
    from reviews.services import public_replies

    return public_replies()


def _describe_review_reply(reply):
    review = reply.review
    hotspot = review.hotspot
    public = not reply.is_held and _public_review_replies().filter(pk=reply.pk).exists()
    return {
        "author": reply.author.username,
        "author_id": reply.author_id,
        "text": reply.body,
        "rating": None,
        "reference": (
            f"Reply to {review.author.username}'s review of "
            f"{hotspot.display_name} (NYC ID {hotspot.pk})"
        ),
        "url": f"{hotspot.get_absolute_url()}#reply-{reply.pk}" if public else "",
        "created_at": reply.created_at,
        "is_demo": False,
        "is_held": reply.is_held,
        "is_public": public,
        # Replies can't be edited, so their creation time identifies the text.
        "version": reply.created_at.isoformat(),
    }


def _held_review_replies():
    from reviews.models import ReviewReply

    return ReviewReply.objects.filter(is_held=True)


def _set_review_reply_held(reply, held):
    from reviews.models import ReviewReply

    ReviewReply.objects.filter(pk=reply.pk).update(is_held=held)
    reply.is_held = held


REVIEW_REPLY = FlaggableType(
    key="reply",
    label="Review reply",
    model_label="reviews.ReviewReply",
    public_queryset=_public_review_replies,
    describe=_describe_review_reply,
    set_held=_set_review_reply_held,
    held_queryset=_held_review_replies,
)


# --- E08 discussion forum ----------------------------------------------------


def _public_posts():
    from forum.services import public_posts

    return public_posts()


def _describe_post(post):
    return {
        "author": post.author.username,
        "author_id": post.author_id,
        "text": f"{post.title}\n\n{post.body}",
        "rating": None,
        "reference": (
            f"Discussion: {post.title}"
            + (f" · {post.hotspot.display_name}" if post.hotspot_id else "")
        ),
        "url": "" if post.is_held else post.get_absolute_url(),
        "created_at": post.created_at,
        "is_demo": False,
        "is_held": post.is_held,
        "is_public": not post.is_held,
        "version": post.updated_at.isoformat(),
    }


def _held_posts():
    from forum.models import ForumPost

    return ForumPost.objects.filter(is_held=True)


def _set_post_held(post, held):
    from forum.models import ForumPost

    # Keep updated_at unchanged: it is the version administrators approve.
    ForumPost.objects.filter(pk=post.pk).update(is_held=held)
    post.is_held = held


def _post_removal_effect(post):
    count = post.comments.count()
    if not count:
        return ""
    return f"Its {count} comment{'s' if count != 1 else ''} and replies are removed with it."


def _public_comments():
    from forum.services import public_comments

    return public_comments()


def _describe_comment(comment):
    post = comment.post
    public = not comment.is_held and not post.is_held
    return {
        "author": comment.author.username,
        "author_id": comment.author_id,
        "text": comment.body,
        "rating": None,
        "reference": f"{'Reply' if comment.parent_id else 'Comment'} on “{post.title}”",
        "url": f"{post.get_absolute_url()}#comment-{comment.pk}" if public else "",
        "created_at": comment.created_at,
        "is_demo": False,
        "is_held": comment.is_held,
        "is_public": public,
        # Comments can't be edited, so their creation time identifies the text.
        "version": comment.created_at.isoformat(),
    }


def _held_comments():
    from forum.models import ForumComment

    return ForumComment.objects.filter(is_held=True)


def _set_comment_held(comment, held):
    from forum.models import ForumComment

    ForumComment.objects.filter(pk=comment.pk).update(is_held=held)
    comment.is_held = held


def _comment_removal_effect(comment):
    count = comment.replies.count()
    if not count:
        return ""
    return f"Its {count} repl{'ies' if count != 1 else 'y'} are removed with it."


FORUM_POST = FlaggableType(
    key="post",
    label="Discussion post",
    model_label="forum.ForumPost",
    public_queryset=_public_posts,
    describe=_describe_post,
    set_held=_set_post_held,
    held_queryset=_held_posts,
    removal_effect=_post_removal_effect,
)

FORUM_COMMENT = FlaggableType(
    key="comment",
    label="Discussion comment",
    model_label="forum.ForumComment",
    public_queryset=_public_comments,
    describe=_describe_comment,
    set_held=_set_comment_held,
    held_queryset=_held_comments,
    removal_effect=_comment_removal_effect,
)

_TYPES = {
    flaggable.key: flaggable
    for flaggable in (REVIEW, REVIEW_REPLY, FORUM_POST, FORUM_COMMENT)
}


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
