from django import forms

from hotspots.models import Hotspot

from .models import ForumPost, ForumComment


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


class ForumCommentForm(forms.ModelForm):
    class Meta:
        model = ForumComment
        fields = ("body",)
        labels = {"body": "Your comment"}
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4, "maxlength": 2000}),
        }
        help_texts = {"body": "Be helpful and respectful. Up to 2,000 characters."}
