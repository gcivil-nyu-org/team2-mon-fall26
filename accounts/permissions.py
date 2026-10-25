"""Shared access checks for contribution and administrator features.

Use these instead of ad hoc checks so every Epic enforces roles the same way:

- Contribution views (E03 reviews, E05 flags, ...): ``@contributor_required``
  or ``ContributorRequiredMixin``. Visitors are sent to the login page with
  ``?next=`` set, so they return to the action after signing in (US09).
- Administrator views (E04 data management, E05 moderation, ...):
  ``@administrator_required`` or ``AdministratorRequiredMixin``. Visitors are
  sent to log in; signed-in non-administrators get 403, even by direct URL (US10).
"""
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .roles import is_administrator, is_contributor


def contributor_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_contributor(request.user):
            return redirect_to_login(request.get_full_path())
        return view_func(request, *args, **kwargs)

    return wrapped


def administrator_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_contributor(request.user):
            return redirect_to_login(request.get_full_path())
        if not is_administrator(request.user):
            raise PermissionDenied("Administrator access is required.")
        return view_func(request, *args, **kwargs)

    return wrapped


class ContributorRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not is_contributor(request.user):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class AdministratorRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not is_administrator(request.user):
            # AccessMixin redirects visitors to login and raises 403 for signed-in users.
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
