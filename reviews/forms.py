from django import forms

from .models import Review

RATING_CHOICES = [(value, f"{value} star{'s' if value > 1 else ''}") for value in range(5, 0, -1)]


class ReviewForm(forms.ModelForm):
    """US11: a required 1-5 rating and an optional written review."""

    rating = forms.TypedChoiceField(
        label="Your rating",
        choices=RATING_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={"required": "Choose a rating from 1 to 5 stars."},
    )
    body = forms.CharField(
        label="Your review (optional)",
        required=False,
        max_length=2000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 5, "maxlength": 2000}),
        help_text="Share your first-hand experience with this hotspot. Up to 2,000 characters.",
    )

    class Meta:
        model = Review
        fields = ("rating", "body")
