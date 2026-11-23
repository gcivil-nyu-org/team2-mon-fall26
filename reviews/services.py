from django.conf import settings
from django.db.models import Avg, Count, Q

from .models import Review, ReviewReply


def visible_reviews():
    """Reviews the public may see: never held for moderation (E05); demo rows only in demo mode."""
    reviews = Review.objects.filter(is_held=False)
    return reviews if settings.DEMO_MODE else reviews.filter(is_demo=False)


def public_replies():
    """Replies anyone can see: not held, under a public review of an active hotspot."""
    replies = ReviewReply.objects.filter(
        is_held=False, review__is_held=False, review__hotspot__is_active=True
    ).exclude(review__body="")
    return replies if settings.DEMO_MODE else replies.filter(review__is_demo=False)


def rating_summary(reviews):
    """Aggregate every rating, including ratings with no written review."""
    result = reviews.aggregate(
        average=Avg("rating"),
        count=Count("pk"),
        review_count=Count("pk", filter=~Q(body="")),
        demo_count=Count("pk", filter=Q(is_demo=True)),
    )
    return {
        "average": (
            round(float(result["average"]), 1)
            if result["average"] is not None
            else None
        ),
        "count": result["count"],
        "review_count": result["review_count"],
        "has_demo_reviews": result["demo_count"] > 0,
    }
