from django import forms

from .models import Reason


class FlagForm(forms.Form):
    """US21: why a contributor thinks an item is inappropriate or misleading."""

    reason = forms.ChoiceField(
        label="What's wrong with this content?",
        choices=Reason.choices,
        widget=forms.RadioSelect,
        error_messages={"required": "Choose a reason for flagging."},
    )
    note = forms.CharField(
        label="Details (optional)",
        required=False,
        max_length=500,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
        help_text="Anything that will help an administrator decide. Up to 500 characters.",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("reason") == Reason.OTHER and not cleaned.get("note"):
            self.add_error("note", "Describe the problem when you choose “Something else”.")
        return cleaned


class RemovalForm(forms.Form):
    """US20: the moderation reason recorded with every removal."""

    reason = forms.ChoiceField(
        label="Moderation reason",
        choices=[("", "Choose a reason")] + list(Reason.choices),
        error_messages={"required": "Choose a moderation reason."},
    )
    note = forms.CharField(
        label="Note for the moderation log (optional)",
        required=False,
        max_length=500,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
        help_text="Only administrators can see this note. It is not sent to the author.",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("reason") == Reason.OTHER and not cleaned.get("note"):
            self.add_error("note", "Explain the reason when you choose “Something else”.")
        return cleaned
