from django.conf import settings
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from reviews.models import Review, ReviewVote
from reviews.services import rating_summary, visible_reviews

from .filters import active_filter_chips, apply_filters, filter_options, read_params
from .models import Hotspot


def _map_settings():
    return {
        "demo_mode": settings.DEMO_MODE,
        "tile_url": settings.MAP_TILE_URL,
        "tile_attribution": settings.MAP_ATTRIBUTION,
    }


def _serialize_hotspot(hotspot, summary):
    return {
        "id": hotspot.pk,
        "name": hotspot.display_name,
        "latitude": float(hotspot.latitude),
        "longitude": float(hotspot.longitude),
        "location": hotspot.location_description,
        "borough": hotspot.borough,
        "neighborhood": hotspot.neighborhood_name,
        "provider": hotspot.provider,
        "access_type": hotspot.access_type,
        "location_type": hotspot.location_type,
        "ssid": hotspot.ssid,
        "profile_url": hotspot.get_absolute_url(),
        "average_rating": summary["average"],
        "rating_count": summary["count"],
        "review_count": summary["review_count"],
        "has_demo_reviews": summary["has_demo_reviews"],
        "source_url": hotspot.source_url,
        "source_acquired_on": hotspot.source_acquired_on.isoformat(),
    }


def _map_data(hotspots):
    aggregates = {
        row["hotspot_id"]: row
        for row in visible_reviews()
        .filter(hotspot__in=hotspots)
        .order_by()
        .values("hotspot_id")
        .annotate(
            average=Avg("rating"),
            count=Count("pk"),
            review_count=Count("pk", filter=~Q(body="")),
            demo_count=Count("pk", filter=Q(is_demo=True)),
        )
    }
    records = []
    for hotspot in hotspots:
        row = aggregates.get(hotspot.pk)
        summary = {
            "average": round(float(row["average"]), 1) if row else None,
            "count": row["count"] if row else 0,
            "review_count": row["review_count"] if row else 0,
            "has_demo_reviews": bool(row and row["demo_count"]),
        }
        records.append(_serialize_hotspot(hotspot, summary))
    if settings.DEMO_MODE:
        records.sort(key=lambda record: record["id"] != 1344)
    return records


@require_GET
def map_view(request):
    active_hotspots = Hotspot.objects.filter(is_active=True)
    filters = read_params(request.GET)
    hotspots = apply_filters(active_hotspots, filters)
    map_data = _map_data(hotspots)
    total_count = active_hotspots.count()
    context = {
        **_map_settings(),
        "hotspots": hotspots,
        "map_data": map_data,
        "hotspot_count": len(map_data),
        "total_count": total_count,
        "provider_count": len({item["provider"] for item in map_data}),
        "borough_count": len({item["borough"] for item in map_data}),
        "filters": filters,
        "is_filtered": bool(filters),
        "filter_options": filter_options(active_hotspots) if total_count else {},
        "filter_chips": active_filter_chips(filters, request.path),
    }
    return render(request, "hotspots/map.html", context)


@require_GET
def detail(request, pk):
    hotspot = get_object_or_404(Hotspot, pk=pk, is_active=True)
    all_reviews = visible_reviews().filter(hotspot=hotspot)
    summary = rating_summary(all_reviews)
    written = (
        all_reviews.exclude(body="")
        .select_related("author")
        .annotate(upvote_count=Count("votes"))
    )
    voted_ids = set()
    user_review = None
    if request.user.is_authenticated:
        voted_ids = set(
            ReviewVote.objects.filter(user=request.user, review__hotspot=hotspot).values_list(
                "review_id", flat=True
            )
        )
        user_review = Review.objects.filter(hotspot=hotspot, author=request.user, is_demo=False).first()
    context = {
        **_map_settings(),
        "hotspot": hotspot,
        "reviews": written,
        "voted_ids": voted_ids,
        "user_review": user_review,
        "rating_summary": summary,
        "profile_map_data": _serialize_hotspot(hotspot, summary),
    }
    return render(request, "hotspots/detail.html", context)


@require_GET
def hotspot_data(request):
    filters = read_params(request.GET)
    records = _map_data(apply_filters(Hotspot.objects.filter(is_active=True), filters))
    return JsonResponse({"count": len(records), "filters": filters, "hotspots": records})
