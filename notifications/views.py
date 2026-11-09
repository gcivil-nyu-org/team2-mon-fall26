from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.permissions import contributor_required

from . import services
from .forms import PreferenceForm
from .models import Notification, NotificationPreference

PAGE_SIZE = 20


@contributor_required
@require_GET
def inbox(request):
    notifications = Notification.objects.filter(recipient=request.user)
    if request.GET.get("show") == "unread":
        notifications = notifications.filter(read_at__isnull=True)
    page = Paginator(notifications, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "notifications/inbox.html",
        {
            "page": page,
            "show_unread": request.GET.get("show") == "unread",
            "has_unread": Notification.objects.filter(
                recipient=request.user, read_at__isnull=True
            ).exists(),
        },
    )


@contributor_required
@require_GET
def open_notification(request, pk):
    """Mark one notification read and go to its hotspot, review or discussion."""
    notification = get_object_or_404(
        Notification.objects.select_related("hotspot", "content_type"),
        pk=pk,
        recipient=request.user,
    )
    services.mark_read(Notification.objects.filter(pk=notification.pk))
    url = services.target_url(notification)
    if url is None:
        messages.info(
            request,
            "That content is no longer available. It may have been deleted, "
            "removed by a moderator, or its hotspot may have been retired.",
        )
        return redirect("notifications:inbox")
    return redirect(url)


@contributor_required
@require_POST
def mark_all_read(request):
    count = services.mark_read(Notification.objects.filter(recipient=request.user))
    if count:
        messages.success(request, "All notifications are marked as read.")
    return redirect("notifications:inbox")


@contributor_required
@require_http_methods(["GET", "POST"])
def preferences(request):
    preference = NotificationPreference.objects.filter(
        user=request.user
    ).first() or NotificationPreference(user=request.user)
    form = PreferenceForm(request.POST or None, instance=preference)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your notification preferences have been saved.")
        return redirect("notifications:inbox")
    return render(request, "notifications/preferences.html", {"form": form})
