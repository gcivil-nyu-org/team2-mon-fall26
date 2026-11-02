from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.permissions import contributor_required
from hotspots.models import Hotspot

from .models import AvailabilityReport


@contributor_required
@require_POST
def submit_report(request, hotspot_pk):
    hotspot = get_object_or_404(Hotspot, pk=hotspot_pk, is_active=True)
    destination = f"{hotspot.get_absolute_url()}#availability"
    status = request.POST.get("status")
    if status not in AvailabilityReport.Status.values:
        messages.error(request, "Choose Working or Unavailable.")
        return redirect(destination)
    AvailabilityReport.objects.create(
        hotspot=hotspot, reporter=request.user, status=status
    )
    messages.success(request, "Thanks. Your availability report has been saved.")
    return redirect(destination)
