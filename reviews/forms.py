from django import forms

from moderation.automod import blocking_problems

from .models import Review, ReviewReply

RATING_CHOICES = [
    (value, f"{value} star{'s' if value > 1 else ''}") for value in range(5, 0, -1)
]


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

    def clean_body(self):
        # E05 tier 1: clear-cut problems are rejected here and nothing is saved.
        body = self.cleaned_data["body"]
        problems = blocking_problems(body)
        if problems:
            raise forms.ValidationError(problems)
        return body


class ReviewReplyForm(forms.ModelForm):
    """A reply to someone's written review. The E05 checks apply as for comments."""

    body = forms.CharField(
        label="Your reply",
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 1000}),
        help_text="Be helpful and respectful. Up to 1,000 characters.",
        error_messages={"required": "Please enter a reply before posting."},
    )

    class Meta:
        model = ReviewReply
        fields = ("body",)

    def clean_body(self):
        # E05 tier 1: clear-cut problems are rejected here and nothing is saved.
        body = self.cleaned_data["body"]
        problems = blocking_problems(body, "reply")
        if problems:
            raise forms.ValidationError(problems)
        return body
