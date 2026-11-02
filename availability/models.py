from django.conf import settings
from django.db import models
from django.utils import timezone


class AvailabilityReport(models.Model):
    """US22: one community observation that a hotspot was working or unavailable.

    Reports are an append-only log, kept separate from overall experience ratings
    (reviews.Review). Each row stores its source (the reporter) and a timestamp.
    """

    class Status(models.TextChoices):
        WORKING = "working", "Working"
        UNAVAILABLE = "unavailable", "Unavailable"

    hotspot = models.ForeignKey(
        "hotspots.Hotspot", on_delete=models.CASCADE, related_name="availability_reports"
    )
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=12, choices=Status.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["hotspot", "created_at"], name="availability_hotspot_time")]

    def __str__(self):
        return f"{self.status} for {self.hotspot_id} by {self.reporter_id}"
