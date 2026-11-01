from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    path("content/<slug:kind>/<int:pk>/flag/", views.flag_content, name="flag"),
    path("manage/moderation/", views.moderation_queue, name="queue"),
    path("manage/moderation/<slug:kind>/<int:pk>/remove/", views.remove_content, name="remove"),
    path("manage/moderation/<slug:kind>/<int:pk>/dismiss/", views.dismiss_flags, name="dismiss"),
]
