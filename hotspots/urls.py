from django.urls import path

from . import views

app_name = "hotspots"

urlpatterns = [
    path("hotspots/<int:pk>/follow/", views.follow, name="follow"),
    path("hotspots/<int:pk>/unfollow/", views.unfollow, name="unfollow"),
    path("", views.map_view, name="map"),
    path("hotspots/<int:pk>/", views.detail, name="detail"),
    path("api/hotspots/", views.hotspot_data, name="data"),
]