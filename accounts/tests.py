from io import StringIO

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path, reverse

from hotspots.tests import make_hotspot
from reviews.models import Review

from .permissions import administrator_required, contributor_required
from .roles import (
    ADMINISTRATOR,
    ADMINISTRATORS_GROUP,
    CONTRIBUTOR,
    CONTRIBUTORS_GROUP,
    VISITOR,
    grant_administrator,
    is_administrator,
    role_for,
)

User = get_user_model()
PASSWORD = "Transit-Wifi-2026!"


@contributor_required
def contribute_stub(request):
    return HttpResponse("contribution form")


@administrator_required
def admin_stub(request):
    return HttpResponse("admin tool")


# Stand-ins for E03/E04 views, so access rules are tested before those views exist.
urlpatterns = [
    path("contribute/", contribute_stub, name="contribute_stub"),
    path("admin-tool/", admin_stub, name="admin_stub"),
    path("", include("config.urls")),
]


def make_user(username="alex", password=PASSWORD, **fields):
    fields.setdefault("email", f"{username}@example.com")
    return User.objects.create_user(username=username, password=password, **fields)


def make_administrator(username="admin"):
    user = make_user(username)
    grant_administrator(user)
    return user


def signup_data(**overrides):
    data = {
        "username": "newcontributor",
        "email": "new@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class RoleGroupMigrationTests(TestCase):
    def test_role_groups_exist_after_migration(self):
        self.assertTrue(Group.objects.filter(name=CONTRIBUTORS_GROUP).exists())
        self.assertTrue(Group.objects.filter(name=ADMINISTRATORS_GROUP).exists())


class SignUpTests(TestCase):
    """US06 / #16"""

    url = reverse("accounts:signup")

    def test_signup_form_is_available_to_visitors(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create an account")
        self.assertEqual(list(response.context["form"].fields), ["username", "email", "password1", "password2"])

    def test_successful_signup_creates_contributor_and_signs_in(self):
        response = self.client.post(self.url, signup_data())
        self.assertRedirects(response, reverse("hotspots:map"))
        user = User.objects.get(username="newcontributor")
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.groups.filter(name=CONTRIBUTORS_GROUP).exists())
        self.assertEqual(role_for(user), CONTRIBUTOR)
        self.assertFalse(user.is_staff)
        self.assertEqual(int(self.client.session[SESSION_KEY]), user.pk)

    def test_password_is_stored_as_a_salted_hash(self):
        self.client.post(self.url, signup_data())
        user = User.objects.get(username="newcontributor")
        self.assertNotIn(PASSWORD, user.password)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(PASSWORD))

    def test_duplicate_username_shows_clear_error(self):
        make_user("Alex")
        response = self.client.post(self.url, signup_data(username="alex"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].errors["username"], ["A user with that username already exists."])
        self.assertEqual(User.objects.filter(username__iexact="alex").count(), 1)

    def test_duplicate_email_is_rejected_regardless_of_case(self):
        make_user("alex", email="alex@example.com")
        response = self.client.post(self.url, signup_data(email="ALEX@Example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertFalse(User.objects.filter(username="newcontributor").exists())

    def test_invalid_details_show_errors_and_create_nothing(self):
        cases = {
            "missing username": (signup_data(username=""), "username"),
            "invalid username": (signup_data(username="bad name!"), "username"),
            "missing email": (signup_data(email=""), "email"),
            "invalid email": (signup_data(email="not-an-email"), "email"),
            "mismatched passwords": (signup_data(password2="Different-Pass-99"), "password2"),
            "short password": (signup_data(password1="Ab1!", password2="Ab1!"), "password2"),
            "common password": (signup_data(password1="password123", password2="password123"), "password2"),
            "numeric password": (signup_data(password1="8675309123", password2="8675309123"), "password2"),
        }
        for label, (data, field) in cases.items():
            with self.subTest(label):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.assertContains(response, "Please fix the highlighted field")
        self.assertFalse(User.objects.exists())

    def test_signup_returns_to_safe_next_url_only(self):
        hotspot_url = make_hotspot().get_absolute_url()
        response = self.client.post(f"{self.url}?next={hotspot_url}", signup_data())
        self.assertRedirects(response, hotspot_url)
        self.client.logout()
        response = self.client.post(
            f"{self.url}?next=https://evil.example.com/",
            signup_data(username="second", email="second@example.com"),
        )
        self.assertRedirects(response, reverse("hotspots:map"))

    def test_signed_in_user_is_redirected_away_from_signup(self):
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(self.url), reverse("hotspots:map"))


class LoginTests(TestCase):
    """US07 / #17"""

    url = reverse("accounts:login")

    def setUp(self):
        self.user = make_user()

    def test_login_form_is_available_to_visitors(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form method="post"', html=False)

    def test_valid_credentials_sign_in_and_show_signed_in_state(self):
        response = self.client.post(self.url, {"username": "alex", "password": PASSWORD}, follow=True)
        self.assertRedirects(response, reverse("hotspots:map"))
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)
        self.assertContains(response, "Signed in as alex.")
        self.assertContains(response, "<strong>alex</strong>", html=True)
        self.assertContains(response, "Log out")

    def test_invalid_credentials_show_one_generic_error(self):
        wrong_password = self.client.post(self.url, {"username": "alex", "password": "nope"})
        unknown_user = self.client.post(self.url, {"username": "nobody", "password": PASSWORD})
        for response in (wrong_password, unknown_user):
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(SESSION_KEY, self.client.session)
            form = response.context["form"]
            self.assertEqual(form.non_field_errors(), ["The username or password is incorrect. Please try again."])
            self.assertNotIn("username", form.errors)
            self.assertNotIn("password", form.errors)

    def test_inactive_account_gets_the_same_generic_error(self):
        make_user("dormant", is_active=False)
        response = self.client.post(self.url, {"username": "dormant", "password": PASSWORD})
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertContains(response, "The username or password is incorrect.")

    def test_login_follows_safe_next_and_ignores_external_next(self):
        hotspot_url = make_hotspot().get_absolute_url()
        response = self.client.post(self.url, {"username": "alex", "password": PASSWORD, "next": hotspot_url})
        self.assertRedirects(response, hotspot_url)
        self.client.logout()
        response = self.client.post(
            self.url, {"username": "alex", "password": PASSWORD, "next": "https://evil.example.com/"}
        )
        self.assertRedirects(response, reverse("hotspots:map"))

    @override_settings(ROOT_URLCONF=__name__)
    def test_signed_in_user_can_access_contribution_features(self):
        self.client.post(reverse("accounts:login"), {"username": "alex", "password": PASSWORD})
        response = self.client.get(reverse("contribute_stub"))
        self.assertEqual(response.status_code, 200)


class LogoutTests(TestCase):
    """US08 / #18"""

    url = reverse("accounts:logout")

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_logout_option_is_visible_to_signed_in_users_only(self):
        response = self.client.get(reverse("hotspots:map"))
        self.assertContains(response, f'action="{self.url}"')
        self.client.logout()
        response = self.client.get(reverse("hotspots:map"))
        self.assertNotContains(response, f'action="{self.url}"')
        self.assertContains(response, "Log in")

    def test_logout_ends_session_and_returns_to_public_map(self):
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, reverse("hotspots:map"))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertContains(response, "You have been logged out.")

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)

    @override_settings(ROOT_URLCONF=__name__)
    def test_contribution_features_are_unavailable_after_logout(self):
        self.assertEqual(self.client.get(reverse("contribute_stub")).status_code, 200)
        self.client.post(reverse("accounts:logout"))
        response = self.client.get(reverse("contribute_stub"))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={reverse('contribute_stub')}", fetch_redirect_response=False
        )


class ContributionSignInTests(TestCase):
    """US09 / #19"""

    def setUp(self):
        self.hotspot = make_hotspot()
        self.profile_url = self.hotspot.get_absolute_url()

    def test_visitors_can_browse_search_filter_and_read_reviews(self):
        author = make_user("reviewer")
        Review.objects.create(hotspot=self.hotspot, author=author, rating=4, body="Solid signal near the fountain.")
        public_pages = [
            reverse("hotspots:map"),
            f"{reverse('hotspots:map')}?q=bryant&borough=Manhattan",
            reverse("hotspots:data"),
            self.profile_url,
        ]
        for url in public_pages:
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(self.profile_url), "Solid signal near the fountain.")

    def test_visitor_is_prompted_to_sign_in_or_sign_up_to_rate(self):
        response = self.client.get(self.profile_url)
        next_param = f"?next={self.profile_url}%23contribute"
        self.assertContains(response, "Sign in to rate or review this hotspot.")
        self.assertContains(response, f'href="{reverse("accounts:login")}{next_param}"')
        self.assertContains(response, f'href="{reverse("accounts:signup")}{next_param}"')

    def test_signing_in_returns_the_user_to_the_hotspot_they_started_from(self):
        make_user()
        next_url = f"{self.profile_url}#contribute"
        response = self.client.post(
            reverse("accounts:login"), {"username": "alex", "password": PASSWORD, "next": next_url}
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        page = self.client.get(self.profile_url)
        self.assertNotContains(page, "Sign in to rate or review this hotspot.")
        self.assertContains(page, "signed in as <strong>alex</strong>")

    def test_signing_up_returns_the_user_to_the_hotspot_they_started_from(self):
        next_url = f"{self.profile_url}#contribute"
        signup_page = self.client.get(reverse("accounts:signup"), {"next": next_url})
        self.assertContains(signup_page, f'name="next" value="{next_url}"')
        response = self.client.post(reverse("accounts:signup"), {**signup_data(), "next": next_url})
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    @override_settings(ROOT_URLCONF=__name__)
    def test_contribution_views_send_visitors_to_login_with_return_path(self):
        response = self.client.get(reverse("contribute_stub"))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={reverse('contribute_stub')}", fetch_redirect_response=False
        )


class AdministratorAccessTests(TestCase):
    """US10 / #20"""

    def setUp(self):
        self.contributor = make_user("contributor")
        self.administrator = make_administrator()
        self.superuser = User.objects.create_superuser("root", "root@example.com", PASSWORD)
        self.admin_url = reverse("accounts:admin_home")

    def test_system_distinguishes_three_roles(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(role_for(AnonymousUser()), VISITOR)
        self.assertEqual(role_for(self.contributor), CONTRIBUTOR)
        self.assertEqual(role_for(self.administrator), ADMINISTRATOR)
        self.assertEqual(role_for(self.superuser), ADMINISTRATOR)
        self.assertEqual(role_for(make_user("dormant", is_active=False)), VISITOR)

    def test_administrators_can_use_the_admin_area(self):
        for user in (self.administrator, self.superuser):
            with self.subTest(user.username):
                self.client.force_login(user)
                response = self.client.get(self.admin_url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Administration")
                self.assertContains(response, "contributor")

    def test_admin_link_is_visible_to_administrators_only(self):
        self.client.force_login(self.administrator)
        self.assertContains(self.client.get(reverse("hotspots:map")), f'href="{self.admin_url}"')
        self.client.force_login(self.contributor)
        self.assertNotContains(self.client.get(reverse("hotspots:map")), f'href="{self.admin_url}"')
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("hotspots:map")), f'href="{self.admin_url}"')

    def test_contributors_are_refused_admin_area_by_direct_url(self):
        self.client.force_login(self.contributor)
        response = self.client.get(self.admin_url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "You don't have access to this page", status_code=403)

    def test_visitors_are_sent_to_login_for_admin_area(self):
        response = self.client.get(self.admin_url)
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={self.admin_url}", fetch_redirect_response=False
        )

    @override_settings(ROOT_URLCONF=__name__)
    def test_administrator_required_decorator_protects_other_admin_tools(self):
        url = reverse("admin_stub")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.contributor)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.administrator)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_contributors_cannot_use_django_admin(self):
        self.client.force_login(self.contributor)
        response = self.client.get(reverse("admin:index"))
        self.assertRedirects(
            response, f"{reverse('admin:login')}?next={reverse('admin:index')}", fetch_redirect_response=False
        )
        self.client.force_login(self.administrator)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_set_administrator_command_grants_and_revokes(self):
        out = StringIO()
        call_command("set_administrator", "CONTRIBUTOR", stdout=out)
        self.contributor.refresh_from_db()
        self.assertTrue(is_administrator(self.contributor))
        self.assertTrue(self.contributor.is_staff)
        self.assertIn("is now an administrator", out.getvalue())

        call_command("set_administrator", "contributor", "--revoke", stdout=StringIO())
        self.contributor = User.objects.get(pk=self.contributor.pk)
        self.assertFalse(is_administrator(self.contributor))
        self.assertFalse(self.contributor.is_staff)

    def test_set_administrator_command_rejects_unknown_accounts_and_superuser_revoke(self):
        with self.assertRaisesMessage(CommandError, "No account named"):
            call_command("set_administrator", "ghost", stdout=StringIO())
        with self.assertRaisesMessage(CommandError, "is a superuser"):
            call_command("set_administrator", "root", "--revoke", stdout=StringIO())
