"""Sorting for search and filter results (E06 US24)."""

from django.db.models import Avg

from availability.services import availability_by_hotspot
from reviews.services import visible_reviews

SORTS = {
    "rating": "Highest rating",
    "rating_asc": "Lowest rating",
    "reliability": "Most reliable",
}


def sort_hotspots(hotspots, sort):
    """Order hotspots by the selected measure. Hotspots without enough data come after those with
    data, and ties keep their incoming order, so filters and sorting combine."""
    if sort not in SORTS:
        return hotspots
    hotspots = list(hotspots)
    ids = [hotspot.pk for hotspot in hotspots]
    if sort in ("rating", "rating_asc"):
        values = dict(
            visible_reviews()
            .filter(hotspot_id__in=ids)
            .order_by()
            .values("hotspot_id")
            .annotate(average=Avg("rating"))
            .values_list("hotspot_id", "average")
        )
    else:
        values = {
            pk: summary["score"] for pk, summary in availability_by_hotspot(ids).items()
        }
    direction = 1 if sort == "rating_asc" else -1
    return sorted(
        hotspots,
        key=lambda hotspot: (
            values.get(hotspot.pk) is None,
            direction * (values.get(hotspot.pk) or 0),
        ),
    )
