from django.conf import settings
from django.db.models import Avg, Count, Q

from .models import Review


def visible_reviews():
    reviews = Review.objects.all()
    return reviews if settings.DEMO_MODE else reviews.filter(is_demo=False)


def rating_summary(reviews):
    """Aggregate every rating, including ratings with no written review."""
    result = reviews.aggregate(
        average=Avg("rating"),
        count=Count("pk"),
        review_count=Count("pk", filter=~Q(body="")),
        demo_count=Count("pk", filter=Q(is_demo=True)),
    )
    return {
        "average": round(float(result["average"]), 1) if result["average"] is not None else None,
        "count": result["count"],
        "review_count": result["review_count"],
        "has_demo_reviews": result["demo_count"] > 0,
    }
