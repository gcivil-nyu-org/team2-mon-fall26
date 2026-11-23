"""Public user profiles: a contributor's public activity, totals and badges.

Only content anyone can already see elsewhere is shown: public written reviews
and replies, public discussion posts and comments, and availability reports
(which name their reporter on hotspot profiles). Star-only ratings stay anonymous
in public (#100), so they are counted only on the user's own profile. Held,
removed and demo content never appears.
"""

from dataclasses import dataclass

from django.db.models import Count, Q

from availability.models import AvailabilityReport
from forum.services import public_comments, public_posts
from moderation.automod import is_trusted
from reviews.models import Review, ReviewVote
from reviews.services import public_replies, visible_reviews

from .roles import is_administrator

RECENT = 5


@dataclass(frozen=True)
class Badge:
    key: str
    label: str
    description: str


def _public_reviews(user):
    return visible_reviews().filter(author=user, is_demo=False, hotspot__is_active=True)


def _badges(user, stats, borough_count):
    badges = []
    if is_administrator(user):
        badges.append(
            Badge("moderator", "Moderator", "Keeps Connect NYC safe and accurate.")
        )
    if is_trusted(user):
        badges.append(
            Badge(
                "trusted",
                "Trusted reviewer",
                "Several published reviews and none removed by moderators.",
            )
        )
    if stats["reviews"]:
        badges.append(
            Badge("first-review", "First review", "Wrote a review of a hotspot.")
        )
    if borough_count >= 3:
        badges.append(
            Badge("explorer", "Borough explorer", "Reviewed hotspots in 3+ boroughs.")
        )
    if stats["helpful_votes"] >= 5:
        badges.append(
            Badge("helpful", "Helpful voice", "Reviews marked helpful 5 or more times.")
        )
    if stats["reports"] >= 5:
        badges.append(
            Badge("scout", "Signal scout", "Reported whether Wi-Fi works 5+ times.")
        )
    if stats["posts"] >= 3:
        badges.append(
            Badge(
                "conversation",
                "Conversation starter",
                "Started 3 or more discussions.",
            )
        )
    return badges


def profile_context(user, viewer):
    """Everything the profile page shows for ``user``, as seen by ``viewer``."""
    reviews = _public_reviews(user)
    written = reviews.exclude(body="")
    replies = public_replies().filter(author=user)
    posts = public_posts().filter(author=user)
    comments = public_comments().filter(author=user)
    reports = AvailabilityReport.objects.filter(reporter=user, hotspot__is_active=True)
    votes = ReviewVote.objects.filter(review__in=written).aggregate(
        up=Count("pk", filter=Q(value=ReviewVote.UP)),
        down=Count("pk", filter=Q(value=ReviewVote.DOWN)),
    )
    stats = {
        "reviews": written.count(),
        "helpful_votes": votes["up"],
        "replies": replies.count(),
        "reports": reports.count(),
        "posts": posts.count(),
        "comments": comments.count(),
    }
    borough_count = (
        written.exclude(hotspot__borough="")
        .values("hotspot__borough")
        .distinct()
        .count()
    )
    is_own = viewer.is_authenticated and viewer.pk == user.pk
    return {
        "profile_user": user,
        "is_own_profile": is_own,
        "is_administrator_profile": is_administrator(user),
        "stats": stats,
        "rating_count": reviews.count() if is_own else None,
        "held_count": (
            Review.objects.filter(author=user, is_held=True).count() if is_own else 0
        ),
        "badges": _badges(user, stats, borough_count),
        "recent_reviews": written.select_related("hotspot").annotate(
            # distinct: votes and replies are joined together.
            upvote_count=Count(
                "votes", filter=Q(votes__value=ReviewVote.UP), distinct=True
            ),
            downvote_count=Count(
                "votes", filter=Q(votes__value=ReviewVote.DOWN), distinct=True
            ),
            reply_count=Count(
                "replies", filter=Q(replies__is_held=False), distinct=True
            ),
        )[:RECENT],
        "recent_posts": posts.select_related("hotspot").annotate(
            comment_count=Count("comments", filter=Q(comments__is_held=False))
        )[:RECENT],
        "recent_replies": replies.select_related(
            "review__hotspot", "review__author"
        ).order_by("-created_at", "-pk")[:RECENT],
        "recent_reports": reports.select_related("hotspot").order_by(
            "-created_at", "-pk"
        )[:RECENT],
    }
