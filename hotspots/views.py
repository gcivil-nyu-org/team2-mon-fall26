from collections import Counter
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.views import redirect_to_login
from django.views.decorators.http import require_GET, require_POST

from availability.models import AvailabilityReport
from availability.services import availability_by_hotspot, hotspot_availability
from reviews.forms import ReviewReplyForm
from reviews.models import Review, ReviewReply, ReviewVote
from moderation.registry import REVIEW, REVIEW_REPLY
from moderation.services import flagged_ids
from reviews.services import rating_summary, visible_reviews

from .filters import active_filter_chips, apply_filters, filter_options, read_params
from .models import Hotspot, HotspotFollow
from .sorting import SORTS, distance_miles, parse_near, sort_hotspots


def _map_settings():
    return {
        "demo_mode": settings.DEMO_MODE,
        "tile_url": settings.MAP_TILE_URL,
        "tile_attribution": settings.MAP_ATTRIBUTION,
    }


def _serialize_hotspot(hotspot, summary, reliability):
    name = hotspot.display_name
    location = hotspot.location_description
    choice_name = name
    if location and hotspot.name == name and name.casefold() != location.casefold():
        choice_name = f"{name} — {location}"
    return {
        "id": hotspot.pk,
        "name": name,
        "choice_label": f"{choice_name} — {hotspot.borough}",
        "latitude": float(hotspot.latitude),
        "longitude": float(hotspot.longitude),
        "location": location,
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
        "reliability_score": reliability["score"],
        "availability_report_count": reliability["report_count"],
    }


def _map_data(hotspots, sort=None, near=None):
    availability = availability_by_hotspot([hotspot.pk for hotspot in hotspots])
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
        records.append(_serialize_hotspot(hotspot, summary, availability[hotspot.pk]))
    origin = parse_near(near)
    for record in records:
        record["distance_miles"] = (
            round(distance_miles(origin, record["latitude"], record["longitude"]), 2)
            if origin
            else None
        )
    label_counts = Counter(record["choice_label"] for record in records)
    for record in records:
        label = record["choice_label"]
        if label_counts[label] > 1:
            record["choice_label"] = f"{label} (Record {record['id']})"
    if settings.DEMO_MODE and not sort:
        records.sort(key=lambda record: record["id"] != 1344)
    return records


def _attach_replies(reviews, user):
    """Give each written review its replies the viewer may see, oldest first.

    Held replies are shown only to their author (E05), like held discussion comments.
    """
    written = {
        review.pk: review for review in reviews if review.body and not review.is_demo
    }
    for review in reviews:
        review.reply_list = []
    if not written:
        return
    replies = ReviewReply.objects.filter(review_id__in=list(written)).select_related(
        "author"
    )
    if user.is_authenticated:
        replies = replies.filter(Q(is_held=False) | Q(author=user))
    else:
        replies = replies.filter(is_held=False)
    for reply in replies:
        written[reply.review_id].reply_list.append(reply)


def _without_location(params, path):
    """The same results without "Near me": no location and no distance sort."""
    remaining = {
        key: value
        for key, value in read_params(params).items()
        if key != "near" and not (key == "sort" and value == "nearest")
    }
    return f"{path}?{urlencode(remaining)}" if remaining else path


@require_GET
def map_view(request):
    active_hotspots = Hotspot.objects.filter(is_active=True)
    filters = read_params(request.GET)
    hotspots = sort_hotspots(
        apply_filters(active_hotspots, filters),
        filters.get("sort"),
        filters.get("near"),
    )
    map_data = _map_data(hotspots, filters.get("sort"), filters.get("near"))
    total_count = active_hotspots.count()
    context = {
        **_map_settings(),
        "map_data": map_data,
        "hotspot_count": len(map_data),
        "total_count": total_count,
        "provider_count": len({item["provider"] for item in map_data}),
        "borough_count": len({item["borough"] for item in map_data}),
        "filters": filters,
        "is_filtered": any(name not in ("sort", "near") for name in filters),
        "near_without_location": filters.get("sort") == "nearest"
        and "near" not in filters,
        "clear_location_url": _without_location(request.GET, request.path),
        "sort_options": SORTS.items(),
        "filter_options": filter_options(active_hotspots) if total_count else {},
        "filter_chips": active_filter_chips(filters, request.path),
    }
    return render(request, "hotspots/map.html", context)


@require_GET
def detail(request, pk):
    hotspot = get_object_or_404(Hotspot, pk=pk, is_active=True)
    all_reviews = visible_reviews().filter(hotspot=hotspot)
    summary = rating_summary(all_reviews)
    availability = hotspot_availability(hotspot)
    reviews = list(
        all_reviews.select_related("author").annotate(
            upvote_count=Count("votes", filter=Q(votes__value=ReviewVote.UP)),
            downvote_count=Count("votes", filter=Q(votes__value=ReviewVote.DOWN)),
        )
    )
    _attach_replies(reviews, request.user)
    voted_ids = set()
    downvoted_ids = set()
    user_review = None
    user_report = None
    is_following = False
    if request.user.is_authenticated:
        for review_id, value in ReviewVote.objects.filter(
            user=request.user, review__hotspot=hotspot
        ).values_list("review_id", "value"):
            (voted_ids if value == ReviewVote.UP else downvoted_ids).add(review_id)
        user_review = Review.objects.filter(
            hotspot=hotspot, author=request.user, is_demo=False
        ).first()
        user_report = AvailabilityReport.objects.filter(
            hotspot=hotspot, reporter=request.user
        ).first()
        is_following = HotspotFollow.objects.filter(
            user=request.user,
            hotspot=hotspot,
        ).exists()
    context = {
        **_map_settings(),
        "hotspot": hotspot,
        "reviews": reviews,
        "voted_ids": voted_ids,
        "downvoted_ids": downvoted_ids,
        "flagged_ids": flagged_ids(request.user, REVIEW),
        "flagged_reply_ids": flagged_ids(request.user, REVIEW_REPLY),
        "reply_form": ReviewReplyForm(),
        "user_review": user_review,
        "user_report": user_report,
        "is_following": is_following,
        "rating_summary": summary,
        "availability": availability,
        "profile_map_data": _serialize_hotspot(hotspot, summary, availability),
    }
    return render(request, "hotspots/detail.html", context)


@require_GET
def hotspot_data(request):
    filters = read_params(request.GET)
    hotspots = sort_hotspots(
        apply_filters(Hotspot.objects.filter(is_active=True), filters),
        filters.get("sort"),
        filters.get("near"),
    )
    records = _map_data(hotspots, filters.get("sort"), filters.get("near"))
    return JsonResponse(
        {"count": len(records), "filters": filters, "hotspots": records}
    )


@require_POST
def follow(request, pk):
    hotspot = get_object_or_404(Hotspot, pk=pk, is_active=True)
    if not request.user.is_authenticated:
        # Login redirects with GET; return to the profile to retry the action.
        return redirect_to_login(hotspot.get_absolute_url())
    HotspotFollow.objects.get_or_create(
        user=request.user,
        hotspot=hotspot,
    )
    return redirect(hotspot.get_absolute_url())


@require_POST
def unfollow(request, pk):
    hotspot = get_object_or_404(Hotspot, pk=pk, is_active=True)
    if not request.user.is_authenticated:
        return redirect_to_login(hotspot.get_absolute_url())
    HotspotFollow.objects.filter(
        user=request.user,
        hotspot=hotspot,
    ).delete()
    return redirect(hotspot.get_absolute_url())


@login_required
@require_GET
def followed(request):
    hotspots = (
        Hotspot.objects.filter(
            followers__user=request.user,
            is_active=True,
        )
        .distinct()
        .order_by("borough", "name", "hotspot_id")
    )

    return render(
        request,
        "hotspots/followed.html",
        {"hotspots": hotspots},
    )
