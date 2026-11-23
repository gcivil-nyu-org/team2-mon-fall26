from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import FormView

from hotspots.models import Hotspot
from moderation.models import ModerationRecord
from moderation.services import held_count, open_item_count
from reviews.models import Review

from notifications.forms import PreferenceForm
from notifications.models import NotificationPreference

from .forms import LoginForm, SignUpForm, ThemeForm
from .models import UserSettings
from .profiles import profile_context
from .permissions import administrator_required, contributor_required
from .roles import ADMINISTRATOR, ROLE_LABELS, role_for

User = get_user_model()


def safe_next_url(request):
    """Return the requested ?next= destination only if it stays on this site."""
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return ""


class SignUpView(FormView):
    """US06: public registration. New accounts become contributors and are signed in."""

    template_name = "accounts/signup.html"
    form_class = SignUpForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return safe_next_url(self.request) or resolve_url(settings.LOGIN_REDIRECT_URL)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = safe_next_url(self.request)
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            self.request,
            f"Welcome to Connect NYC, {user.username}. Your account is ready.",
        )
        return redirect(self.get_success_url())


class AccountLoginView(LoginView):
    """US07: valid credentials sign the user in and return them to ?next= (US09)."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Signed in as {form.get_user().username}.")
        return response


class AccountLogoutView(LogoutView):
    """US08: POST-only logout that ends the session and returns to the public map."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have been logged out.")
        return response


@administrator_required
def admin_home(request):
    """US10: administrator-only area. E04/E05 tools link from here."""
    users = User.objects.prefetch_related("groups").order_by("-date_joined")
    accounts = [
        {"user": account, "role": ROLE_LABELS[role_for(account)]}
        for account in users.filter(is_active=True)[:25]
    ]
    active_users = list(users.filter(is_active=True))
    administrator_count = sum(
        1 for account in active_users if role_for(account) == ADMINISTRATOR
    )
    hotspot_counts = Hotspot.objects.aggregate(
        active=Count("pk", filter=Q(is_active=True)),
        inactive=Count("pk", filter=Q(is_active=False)),
    )
    context = {
        "accounts": accounts,
        "contributor_count": len(active_users) - administrator_count,
        "administrator_count": administrator_count,
        "hotspot_counts": hotspot_counts,
        "review_count": Review.objects.filter(is_demo=False).count(),
        "open_flag_items": open_item_count(),
        "held_count": held_count(),
        "removed_count": ModerationRecord.objects.filter(
            action=ModerationRecord.Action.REMOVED
        ).count(),
    }
    return render(request, "accounts/admin_home.html", context)


# --- Settings (notification preferences and appearance) ---------------------

FOLLOWED_FIELDS = (
    "followed_reviews",
    "followed_availability",
    "followed_availability_alerts",
    "followed_discussions",
)
CONTRIBUTION_FIELDS = ("review_replies", "flag_outcomes")


def _settings_for(user):
    return UserSettings.objects.filter(user=user).first() or UserSettings(user=user)


@contributor_required
@require_http_methods(["GET", "POST"])
def settings_view(request):
    """One page for a signed-in user's notification categories and appearance."""
    preference = NotificationPreference.objects.filter(
        user=request.user
    ).first() or NotificationPreference(user=request.user)
    data = request.POST if request.method == "POST" else None
    theme_form = ThemeForm(data, instance=_settings_for(request.user))
    preference_form = PreferenceForm(data, instance=preference)
    if (
        request.method == "POST"
        and theme_form.is_valid()
        and preference_form.is_valid()
    ):
        theme_form.save()
        preference_form.save()
        messages.success(request, "Your settings have been saved.")
        return redirect("accounts:settings")
    return render(
        request,
        "accounts/settings.html",
        {
            "theme_form": theme_form,
            "followed_fields": [preference_form[name] for name in FOLLOWED_FIELDS],
            "contribution_fields": [
                preference_form[name] for name in CONTRIBUTION_FIELDS
            ],
        },
    )


@contributor_required
@require_POST
def set_theme(request):
    """The header's light/dark switch: save the theme and return to the same page."""
    theme = request.POST.get("theme")
    if theme in UserSettings.Theme.values:
        settings_row = _settings_for(request.user)
        settings_row.theme = theme
        settings_row.save()
    return redirect(safe_next_url(request) or "accounts:settings")


def profile(request, username):
    """A contributor's public profile: totals, badges and recent public activity."""
    user = get_object_or_404(User, username=username, is_active=True)
    return render(request, "accounts/profile.html", profile_context(user, request.user))
