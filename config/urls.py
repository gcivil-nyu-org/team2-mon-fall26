from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("reviews.urls")),
    path("", include("moderation.urls")),
    path("", include("availability.urls")),
    path("forum/", include("forum.urls")),
    path("", include("notifications.urls")),
    path("", include("hotspots.urls")),
]
