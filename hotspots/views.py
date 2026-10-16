from django.conf import settings
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from reviews.services import rating_summary, visible_reviews

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
    hotspots = Hotspot.objects.filter(is_active=True)
    map_data = _map_data(hotspots)
    context = {
        **_map_settings(),
        "hotspots": hotspots,
        "map_data": map_data,
        "hotspot_count": len(map_data),
        "provider_count": len({item["provider"] for item in map_data}),
        "borough_count": len({item["borough"] for item in map_data}),
    }
    return render(request, "hotspots/map.html", context)


@require_GET
def detail(request, pk):
    hotspot = get_object_or_404(Hotspot, pk=pk, is_active=True)
    all_reviews = visible_reviews().filter(hotspot=hotspot)
    summary = rating_summary(all_reviews)
    context = {
        **_map_settings(),
        "hotspot": hotspot,
        "reviews": all_reviews.exclude(body="").select_related("author"),
        "rating_summary": summary,
        "profile_map_data": _serialize_hotspot(hotspot, summary),
    }
    return render(request, "hotspots/detail.html", context)


@require_GET
def hotspot_data(request):
    records = _map_data(Hotspot.objects.filter(is_active=True))
    return JsonResponse({"count": len(records), "hotspots": records})
