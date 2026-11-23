from django.conf import settings
from django.db import models


class UserSettings(models.Model):
    """Per-user display settings. No row means the defaults below."""

    class Theme(models.TextChoices):
        SYSTEM = "system", "Match my device"
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="site_settings",
    )
    theme = models.CharField(
        "Appearance", max_length=10, choices=Theme.choices, default=Theme.SYSTEM
    )

    def __str__(self):
        return f"Settings for {self.user_id}"


def theme_for(user):
    """The saved theme for a signed-in user, ``system`` otherwise."""
    if user is None or not user.is_authenticated:
        return UserSettings.Theme.SYSTEM
    try:
        return user.site_settings.theme
    except UserSettings.DoesNotExist:
        return UserSettings.Theme.SYSTEM


class LoginFailure(models.Model):
    """Shared login cooldown, keyed by an opaque fingerprint of the login name."""

    identity = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
