from io import StringIO
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.permissions import administrator_required
from reviews.models import ReviewVote

from .forms import HotspotEditForm, HotspotImportForm
from .importing import HotspotImportError, import_hotspots
from .models import Hotspot


@administrator_required
@require_GET
def manage_list(request):
    records = Hotspot.objects.all()
    counts = records.aggregate(
        active=Count("pk", filter=Q(is_active=True)),
        retired=Count("pk", filter=Q(is_active=False)),
    )
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "all")
    if status not in {"all", "active", "retired"}:
        status = "all"
    if status != "all":
        records = records.filter(is_active=status == "active")
    if query:
        matches = Q(name__icontains=query) | Q(location_description__icontains=query)
        matches |= Q(provider__icontains=query) | Q(borough__icontains=query)
        if query.isascii() and query.isdigit() and len(query) <= 10:
            matches |= Q(pk=int(query))
        records = records.filter(matches)
    page = Paginator(records.order_by("borough", "name", "hotspot_id"), 50).get_page(
        request.GET.get("page")
    )
    return render(request, "hotspots/manage_list.html", {
        "page_obj": page, "q": query, "status": status,
        "active_count": counts["active"], "retired_count": counts["retired"],
        "query_string": urlencode({"q": query, "status": status}),
    })


@administrator_required
@require_http_methods(["GET", "POST"])
def manage_import(request):
    form = HotspotImportForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = import_hotspots(StringIO(form.csv_text), form.cleaned_data["source_date"])
        except HotspotImportError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request,
                f"Imported {result['total']} official hotspots: {result['created']} created, "
                f"{result['updated']} updated. No records were removed or reactivated.")
            return redirect("hotspots:manage_list")
    return render(request, "hotspots/manage_import.html", {
        "form": form, "source_url": Hotspot.source_url,
    })


@administrator_required
@require_http_methods(["GET", "POST"])
def manage_edit(request, pk):
    hotspot = get_object_or_404(Hotspot, pk=pk)
    form = HotspotEditForm(
        request.POST if request.method == "POST" else None, instance=hotspot,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated {hotspot.display_name}. Visibility is unchanged.")
        return redirect("hotspots:manage_list")
    return render(request, "hotspots/manage_edit.html", {"form": form, "hotspot": hotspot})


@administrator_required
@require_http_methods(["GET", "POST"])
def manage_retire(request, pk):
    hotspot = get_object_or_404(Hotspot, pk=pk)
    if request.method == "POST" and request.POST.get("confirm") == "yes":
        Hotspot.objects.filter(pk=pk).update(is_active=False)
        messages.success(request,
            f"Removed {hotspot.display_name} from public discovery. Reviews and helpful votes are retained.")
        return redirect("hotspots:manage_list")
    context = {
        "hotspot": hotspot,
        "review_count": hotspot.reviews.count(),
        "vote_count": ReviewVote.objects.filter(review__hotspot=hotspot).count(),
    }
    if request.method == "POST":
        messages.error(request, "Confirm removal before changing this hotspot's visibility.")
    return render(request, "hotspots/manage_confirm_retire.html", context)
