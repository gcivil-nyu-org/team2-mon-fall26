from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.discussion_list, name="list"),
    path("posts/new/", views.create_post, name="create"),
    path("posts/<int:pk>/", views.discussion_detail, name="detail"),
    path(
        "posts/<int:pk>/edit/", views.edit_own, {"kind": "discussion"}, name="edit_post"
    ),
    path(
        "posts/<int:pk>/delete/",
        views.delete_own,
        {"kind": "discussion"},
        name="delete_post",
    ),
    path(
        "comments/<int:pk>/edit/",
        views.edit_own,
        {"kind": "comment"},
        name="edit_comment",
    ),
    path(
        "comments/<int:pk>/delete/",
        views.delete_own,
        {"kind": "comment"},
        name="delete_comment",
    ),
    path("posts/<int:post_pk>/comments/", views.add_comment, name="comment"),
    path("posts/<int:post_pk>/vote/", views.toggle_post_vote, name="post_vote"),
    path(
        "comments/<int:comment_pk>/vote/",
        views.toggle_comment_vote,
        name="comment_vote",
    ),
]
