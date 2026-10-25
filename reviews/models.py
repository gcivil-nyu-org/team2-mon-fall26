from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    hotspot = models.ForeignKey(
        "hotspots.Hotspot", on_delete=models.CASCADE, related_name="reviews"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.TextField(blank=True)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_between_one_and_five",
            ),
            models.UniqueConstraint(
                fields=["hotspot", "author"], name="one_review_per_author_per_hotspot"
            ),
        ]

    def __str__(self):
        return f"{self.rating}/5 for {self.hotspot_id} by {self.author_id}"


class ReviewVote(models.Model):
    """US15: one helpful upvote per user per review. There are no downvotes."""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="one_vote_per_user_per_review")
        ]
