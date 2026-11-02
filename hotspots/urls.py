from django.urls import path

from . import management_views, views

app_name = "hotspots"

urlpatterns = [
    path("hotspots/<int:pk>/follow/", views.follow, name="follow"),
    path("hotspots/<int:pk>/unfollow/", views.unfollow, name="unfollow"),
    path("manage/hotspots/", management_views.manage_list, name="manage_list"),
    path("manage/hotspots/import/", management_views.manage_import, name="manage_import"),
    path("manage/hotspots/<int:pk>/edit/", management_views.manage_edit, name="manage_edit"),
    path("manage/hotspots/<int:pk>/remove/", management_views.manage_retire, name="manage_retire"),
    path("", views.map_view, name="map"),
    path("hotspots/<int:pk>/", views.detail, name="detail"),
    path("api/hotspots/", views.hotspot_data, name="data"),
    path("followed/", views.followed, name="followed"),
]
