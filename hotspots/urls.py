from django.urls import path

from . import views

app_name = "hotspots"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("hotspots/<int:pk>/", views.detail, name="detail"),
    path("api/hotspots/", views.hotspot_data, name="data"),
]
