"""Sorting for search and filter results (E06 US24) and by distance ("Near me")."""

from math import asin, cos, radians, sin, sqrt

from django.db.models import Avg

from availability.services import availability_by_hotspot
from reviews.services import visible_reviews

SORTS = {
    "rating": "Highest rating",
    "rating_asc": "Lowest rating",
    "reliability": "Most reliable",
    "nearest": "Nearest to me",
}

EARTH_RADIUS_MILES = 3958.8


def distance_miles(origin, latitude, longitude):
    """Great-circle (haversine) distance in miles from ``origin`` = (lat, lng)."""
    lat1, lng1 = map(radians, origin)
    lat2, lng2 = radians(float(latitude)), radians(float(longitude))
    a = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(a))


def parse_near(value):
    """``"40.7536,-73.9832"`` -> (40.7536, -73.9832), or None if it isn't a location."""
    try:
        latitude, longitude = (float(part) for part in value.split(","))
    except (AttributeError, TypeError, ValueError):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def sort_hotspots(hotspots, sort, near=None):
    """Order hotspots by the selected measure. Hotspots without enough data come after those with
    data, and ties keep their incoming order, so filters and sorting combine.

    ``nearest`` needs ``near`` (the visitor's location); without it the default
    order is kept."""
    if sort not in SORTS:
        return hotspots
    if sort == "nearest":
        origin = parse_near(near)
        if origin is None:
            return hotspots
        return sorted(
            hotspots,
            key=lambda hotspot: distance_miles(
                origin, hotspot.latitude, hotspot.longitude
            ),
        )
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
