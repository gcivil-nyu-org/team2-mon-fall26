from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("healthz/", health, name="health"),
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("reviews.urls")),
    path("", include("moderation.urls")),
    path("", include("availability.urls")),
    path("forum/", include("forum.urls")),
    path("", include("notifications.urls")),
    path("", include("hotspots.urls")),
]
