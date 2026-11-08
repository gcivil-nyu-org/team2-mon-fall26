from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.roles import is_contributor
from hotspots.models import Hotspot
from notifications import services as notify

from .models import AvailabilityReport


@require_POST
def submit_report(request, hotspot_pk):
    hotspot = get_object_or_404(Hotspot, pk=hotspot_pk, is_active=True)
    destination = f"{hotspot.get_absolute_url()}#availability"
    if not is_contributor(request.user):
        # Login returns with GET; let the contributor retry from the profile.
        return redirect_to_login(destination)
    status = request.POST.get("status")
    if status not in AvailabilityReport.Status.values:
        messages.error(request, "Choose Working or Unavailable.")
        return redirect(destination)
    report = AvailabilityReport.objects.create(
        hotspot=hotspot, reporter=request.user, status=status
    )
    notify.availability_reported(report)
    messages.success(request, "Thanks. Your availability report has been saved.")
    return redirect(destination)
