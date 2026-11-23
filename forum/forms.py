from django import forms

from hotspots.models import Hotspot
from moderation.automod import blocking_problems

from .models import ForumPost, ForumComment


def _reject_blocked(text, content):
    problems = blocking_problems(text, content)
    if problems:
        raise forms.ValidationError(problems)
    return text


class ForumPostForm(forms.ModelForm):
    class Meta:
        model = ForumPost
        fields = ("topic_type", "title", "body", "hotspot")
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 180}),
            "body": forms.Textarea(attrs={"rows": 7, "maxlength": 5000}),
        }
        help_texts = {
            "title": "Use a clear, specific title.",
            "body": "Describe your question or start the conversation. Up to 5,000 characters.",
            "hotspot": "Optional. Link an official hotspot without creating a rating or review.",
        }
        labels = {"topic_type": "Post type", "hotspot": "Related hotspot (optional)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hotspot"].queryset = Hotspot.objects.filter(is_active=True)
        self.fields["hotspot"].required = False

    # E05 tier 1: clear-cut problems are rejected here and nothing is saved.
    def clean_title(self):
        return _reject_blocked(self.cleaned_data["title"], "post")

    def clean_body(self):
        return _reject_blocked(self.cleaned_data["body"], "post")


class ForumCommentForm(forms.ModelForm):
    class Meta:
        model = ForumComment
        fields = ("body",)
        labels = {"body": "Your comment"}
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4, "maxlength": 2000}),
        }
        help_texts = {"body": "Be helpful and respectful. Up to 2,000 characters."}

    def clean_body(self):
        return _reject_blocked(self.cleaned_data["body"], "comment")


class ForumPostEditForm(ForumPostForm):
    """An author can correct their title and text without moving the discussion."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["topic_type"], self.fields["hotspot"]
