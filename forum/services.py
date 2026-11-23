"""Which discussion content each viewer may see (E05 holds applied to E08)."""

from django.db.models import Q

from .models import ForumComment, ForumPost


def visible_posts(user=None):
    """Public posts, plus the viewer's own held posts so authors can still see them."""
    posts = ForumPost.objects.all()
    if user is not None and user.is_authenticated:
        return posts.filter(Q(is_held=False) | Q(author=user))
    return posts.filter(is_held=False)


def public_posts():
    return ForumPost.objects.filter(is_held=False, author_removed=False)


def public_comments():
    """Comments anyone can see: not held, on a post that is not held."""
    return ForumComment.objects.filter(is_held=False, post__is_held=False)
