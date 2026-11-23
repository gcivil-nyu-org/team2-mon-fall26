"""Count rejected credentials across application workers and both login forms."""

from datetime import timedelta
from math import ceil

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginFailure

FAILURE_LIMIT = 5
COOLDOWN = timedelta(minutes=2)
FAILURE_RETENTION = timedelta(days=1)
SESSION_DEADLINE = "accounts_login_cooldown_until"


def _identity(username):
    user_model = get_user_model()
    normalized = user_model.normalize_username(username.strip())
    # Use the database's canonical spelling for names its collation treats alike.
    stored = (
        user_model.objects.filter(username=normalized)
        .values_list("username", flat=True)
        .first()
    )
    return salted_hmac(
        "accounts.login.cooldown", (stored or normalized).casefold(), algorithm="sha256"
    ).hexdigest()


def _prune_expired(now):
    expired = LoginFailure.objects.filter(expires_at__lte=now)
    keys = list(expired.order_by("expires_at").values_list("pk", flat=True)[:32])
    if keys:
        expired.filter(pk__in=keys).delete()


class LoginCooldownMixin:
    @property
    def retry_after(self):
        if self.request is None:
            return 0
        deadline = self.request.session.get(SESSION_DEADLINE, 0)
        return max(0, ceil(deadline - timezone.now().timestamp()))

    def _locked(self):
        self.request.login_retry_after = self.retry_after
        return ValidationError(
            "Too many failed attempts. Please wait before trying again.",
            code="cooldown",
        )

    def clean(self):
        if self.retry_after:
            raise self._locked()
        username = self.cleaned_data.get("username")
        if (
            not username
            or not self.cleaned_data.get("password")
            or self.request is None
        ):
            return super().clean()

        now = timezone.now()
        _prune_expired(now)
        key = _identity(username)
        with transaction.atomic():
            attempt, _ = LoginFailure.objects.select_for_update().get_or_create(
                identity=key, defaults={"expires_at": now + FAILURE_RETENTION}
            )
            now = timezone.now()
            if attempt.expires_at <= now:
                attempt.failures = 0
            if attempt.failures < FAILURE_LIMIT:
                try:
                    cleaned = super().clean()
                except ValidationError as exc:
                    error = exc
                    attempt.failures += 1
                    lifetime = (
                        COOLDOWN
                        if attempt.failures == FAILURE_LIMIT
                        else FAILURE_RETENTION
                    )
                    attempt.expires_at = timezone.now() + lifetime
                    attempt.save(update_fields=["failures", "expires_at"])
                else:
                    attempt.delete()
                    self.request.session.pop(SESSION_DEADLINE, None)
                    return cleaned
            if attempt.failures >= FAILURE_LIMIT:
                self.request.session[SESSION_DEADLINE] = attempt.expires_at.timestamp()
                error = self._locked()
        # Raising inside the transaction would undo the failure that we just counted.
        raise error


class LoginCooldownHeaders:
    """Set the same retry response on the public login and the Django admin login."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        seconds = getattr(request, "login_retry_after", None)
        if seconds is not None:
            response.status_code = 429
            response["Retry-After"] = str(seconds)
        return response
