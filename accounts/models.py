from django.db import models


class LoginFailure(models.Model):
    """Shared login cooldown, keyed by an opaque fingerprint of the login name."""

    identity = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
