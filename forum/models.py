from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse


class ForumPost(models.Model):
    class TopicType(models.TextChoices):
        QUESTION = "question", "Question"
        DISCUSSION = "discussion", "Discussion"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_posts",
    )
    topic_type = models.CharField(max_length=16, choices=TopicType.choices)
    title = models.CharField(max_length=180)
    body = models.TextField(max_length=5000)
    hotspot = models.ForeignKey(
        "hotspots.Hotspot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forum_posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("forum:detail", kwargs={"pk": self.pk})


class ForumComment(models.Model):
    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_comments",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"Comment by {self.author_id} on post {self.post_id}"


class ForumVote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_votes",
    )
    post = models.ForeignKey(
        ForumPost,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    comment = models.ForeignKey(
        ForumComment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(post__isnull=False, comment__isnull=True)
                    | Q(post__isnull=True, comment__isnull=False)
                ),
                name="forum_vote_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["user", "post"],
                name="one_user_vote_per_forum_post",
            ),
            models.UniqueConstraint(
                fields=["user", "comment"],
                name="one_user_vote_per_forum_comment",
            ),
        ]
