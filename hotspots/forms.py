from django import forms
from django.utils import timezone

from .importing import BOROUGHS
from .models import Hotspot


MAX_IMPORT_BYTES = 5 * 1024 * 1024


class HotspotImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Official hotspot CSV",
        help_text="Upload a UTF-8 CSV with the NYC source column names (up to 5 MB).",
        widget=forms.FileInput(attrs={"accept": ".csv,text/csv"}),
    )
    source_date = forms.DateField(
        label="Source acquisition date",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="The date this dataset was obtained from NYC Open Data.",
    )

    def clean_csv_file(self):
        uploaded = self.cleaned_data["csv_file"]
        if uploaded.size > MAX_IMPORT_BYTES:
            raise forms.ValidationError("Choose a CSV file no larger than 5 MB.")
        data = uploaded.read(MAX_IMPORT_BYTES + 1)
        if len(data) > MAX_IMPORT_BYTES:
            raise forms.ValidationError("Choose a CSV file no larger than 5 MB.")
        try:
            self.csv_text = data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise forms.ValidationError("Save the CSV as UTF-8 and upload it again.") from exc
        return uploaded

    def clean_source_date(self):
        value = self.cleaned_data["source_date"]
        if value > timezone.localdate():
            raise forms.ValidationError("The acquisition date cannot be in the future.")
        return value


class HotspotEditForm(forms.ModelForm):
    borough = forms.ChoiceField(choices=[(name, name) for name in sorted(BOROUGHS)])

    class Meta:
        model = Hotspot
        fields = (
            "name", "location_description", "latitude", "longitude", "borough",
            "neighborhood_name", "neighborhood_code", "zip_code", "provider",
            "access_type", "location_type", "ssid", "remarks", "activated_on",
        )
        labels = {"ssid": "Wi-Fi network name (SSID)", "activated_on": "Activation date"}
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 3}),
            "activated_on": forms.DateInput(attrs={"type": "date"}),
        }

    def save(self, commit=True):
        hotspot = super().save(commit=False)
        if commit:
            # Preserve identity, provenance and retirement even if another request
            # changes them after this form loaded its instance.
            hotspot.save(update_fields=self.Meta.fields)
        return hotspot
