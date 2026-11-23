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
    # E05: held reviews are hidden from the public and the average until an
    # administrator approves or removes them. Only the author can see them.
    is_held = models.BooleanField(default=False)
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
    """One vote per user per written review: helpful (up) or not helpful (down).

    US15 introduced helpful upvotes; downvotes were added for the review-replies
    increment. Existing votes are upvotes. Votes never change star averages.
    """

    UP = 1
    DOWN = -1
    VALUE_CHOICES = [(UP, "Helpful"), (DOWN, "Not helpful")]

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    value = models.SmallIntegerField(choices=VALUE_CHOICES, default=UP)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["review", "user"], name="one_vote_per_user_per_review"
            ),
            models.CheckConstraint(
                condition=models.Q(value__in=[1, -1]),
                name="review_vote_value_up_or_down",
            ),
        ]


class ReviewReply(models.Model):
    """A reply to someone's written review, shown under it on the hotspot profile.

    Replies are community content: the same E05 checks, flags, holds and removals
    apply as for reviews and discussion comments (see ``moderation.registry``).
    Replies can't be edited, so their creation time identifies their text.
    """

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_replies",
    )
    body = models.TextField(max_length=1000)
    # E05: held replies are shown only to their author until a moderator decides.
    is_held = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"Reply by {self.author_id} to review {self.review_id}"
