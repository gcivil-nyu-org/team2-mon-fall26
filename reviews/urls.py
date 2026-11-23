from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("hotspots/<int:hotspot_pk>/review/", views.create_review, name="create"),
    path("reviews/<int:pk>/edit/", views.edit_review, name="edit"),
    path("reviews/<int:pk>/delete/", views.delete_review, name="delete"),
    path("reviews/<int:pk>/vote/", views.toggle_vote, name="vote"),
    path("reviews/<int:pk>/replies/", views.add_reply, name="reply"),
    path("replies/<int:pk>/delete/", views.delete_reply, name="delete_reply"),
]
