from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.discussion_list, name="list"),
    path("posts/new/", views.create_post, name="create"),
    path("posts/<int:pk>/", views.discussion_detail, name="detail"),
    path("posts/<int:post_pk>/comments/", views.add_comment, name="comment"),
    path("posts/<int:post_pk>/vote/", views.toggle_post_vote, name="post_vote"),
    path("comments/<int:comment_pk>/vote/", views.toggle_comment_vote, name="comment_vote"),
]
