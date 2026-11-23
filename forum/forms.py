from django import forms
from django.core.paginator import Paginator

from hotspots.filters import MAX_QUERY_LENGTH, apply_filters
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

    def __init__(self, *args, hotspot_query="", page_number=1, **kwargs):
        super().__init__(*args, **kwargs)
        active = Hotspot.objects.filter(is_active=True)
        field = self.fields["hotspot"]
        field.queryset = active
        self.hotspot_query = " ".join(hotspot_query.split())[:MAX_QUERY_LENGTH]
        self.hotspot_page = None
        choices = {}
        if self.hotspot_query:
            matches = apply_filters(active, {"q": self.hotspot_query})
            if (
                self.hotspot_query.isascii()
                and self.hotspot_query.isdecimal()
                and len(self.hotspot_query) <= 10
            ):
                matches = matches | active.filter(pk=int(self.hotspot_query))
            self.hotspot_page = Paginator(matches, 25).get_page(page_number)
            choices = {item.pk: item for item in self.hotspot_page}
        # Keep an existing selection when the author searches again or corrects a draft.
        selected = str(self["hotspot"].value() or "")
        if selected.isascii() and selected.isdecimal() and len(selected) <= 10:
            pk = int(selected)
            if pk not in choices:
                item = active.filter(pk=pk).first()
                if item:
                    choices[pk] = item
        field.widget.choices = [("", "No related hotspot")] + [
            (item.pk, f"{item.choice_label} (Record {item.pk})")
            for item in choices.values()
        ]

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
