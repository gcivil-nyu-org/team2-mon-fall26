from datetime import date
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class Hotspot(models.Model):
    class AccessType(models.TextChoices):
        FREE = "Free", "Free"
        LIMITED_FREE = "Limited Free", "Limited Free"
        PARTNER_SITE = "Partner Site", "Partner Site"

    # NYC's stable doitt_id, rather than coordinates, identifies an official record.
    hotspot_id = models.PositiveIntegerField(primary_key=True)
    source_object_id = models.PositiveIntegerField()
    name = models.CharField(max_length=255, null=True, blank=True)
    location_description = models.CharField(max_length=512)
    latitude = models.DecimalField(
        max_digits=16,
        decimal_places=12,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=16,
        decimal_places=12,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    borough = models.CharField(max_length=32)
    neighborhood_name = models.CharField(max_length=255, blank=True)
    neighborhood_code = models.CharField(max_length=32, blank=True)
    zip_code = models.CharField(max_length=16, blank=True)
    provider = models.CharField(max_length=150)
    access_type = models.CharField(max_length=32, choices=AccessType.choices)
    location_type = models.CharField(max_length=150, blank=True)
    ssid = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    source_ref = models.CharField(max_length=255, null=True, blank=True)
    activated_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    source_acquired_on = models.DateField()

    source_name = "NYC Open Data"
    source_url = (
        "https://data.cityofnewyork.us/City-Government/"
        "NYC-Wi-Fi-Hotspot-Locations/yjub-udmw"
    )
    source_last_updated_on = date(2019, 9, 26)

    class Meta:
        ordering = ["borough", "name", "hotspot_id"]

    @property
    def display_name(self):
        # Keep the raw official name, but do not label a map marker only "0".
        if self.name and self.name != "0":
            return self.name
        return f"{self.provider} — {self.location_description}"

    @property
    def location(self):
        return self.location_description

    @property
    def neighborhood(self):
        return self.neighborhood_name

    def get_absolute_url(self):
        return reverse("hotspots:detail", kwargs={"pk": self.pk})

    def __str__(self):
        return self.display_name
