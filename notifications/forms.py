from django import forms

from .models import NotificationPreference


class PreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "followed_reviews",
            "followed_availability",
            "followed_availability_alerts",
            "followed_discussions",
        ]
