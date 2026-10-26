from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView

from hotspots.models import Hotspot
from reviews.models import Review

from .forms import LoginForm, SignUpForm
from .permissions import administrator_required
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
        messages.success(self.request, f"Welcome to Connect NYC, {user.username}. Your account is ready.")
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
    administrator_count = sum(1 for account in active_users if role_for(account) == ADMINISTRATOR)
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
    }
    return render(request, "accounts/admin_home.html", context)
