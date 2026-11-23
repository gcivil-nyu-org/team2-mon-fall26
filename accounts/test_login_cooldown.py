from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from .forms import LoginForm
from .models import LoginFailure
from .tests import PASSWORD, make_user
from .throttling import COOLDOWN, FAILURE_RETENTION, _identity


class LoginCooldownTests(TestCase):
    login = reverse("accounts:login")
    admin_login = reverse("admin:login")

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("Casey")
        cls.other = make_user("Robin")

    def setUp(self):
        self.now = timezone.now()

    def seed(self, username, count, expires_at=None):
        return LoginFailure.objects.create(
            identity=_identity(username),
            failures=count,
            expires_at=expires_at or self.now + FAILURE_RETENTION,
        )

    def test_fifth_failure_starts_two_minute_cooldown_across_both_forms(self):
        row = self.seed("Casey", 3)
        credentials = {"username": "casey", "password": "incorrect fixture"}
        with patch("accounts.throttling.timezone.now", return_value=self.now):
            fourth = self.client.post(self.admin_login, credentials)
            self.assertEqual(fourth.status_code, 200)
            row.refresh_from_db()
            self.assertEqual(row.failures, 4)
            fifth = self.client.post(self.login, credentials)
            self.assertContains(fifth, 'id="login-cooldown"', status_code=429)
            self.assertContains(fifth, "disabled", status_code=429)
            self.assertEqual(fifth["Retry-After"], "120")
            row.refresh_from_db()
            self.assertEqual((row.failures, row.expires_at), (5, self.now + COOLDOWN))

        later = self.now + timedelta(seconds=76)
        with patch("accounts.throttling.timezone.now", return_value=later):
            self.assertContains(self.client.get(self.login), 'data-seconds="44"')
            with patch("django.contrib.auth.forms.authenticate") as authenticate:
                second_browser = Client().post(
                    self.admin_login, {"username": "CASEY", "password": PASSWORD}
                )
                self.assertEqual(second_browser.status_code, 429)
                self.assertEqual(second_browser["Retry-After"], "44")
                self.assertContains(
                    second_browser, 'data-form="login-form"', status_code=429
                )
                authenticate.assert_not_called()
            row.refresh_from_db()
            self.assertEqual(row.expires_at, self.now + COOLDOWN)
            other = Client()
            other.post(self.login, {"username": "Robin", "password": PASSWORD})
            self.assertEqual(int(other.session[SESSION_KEY]), self.other.pk)

        with patch(
            "accounts.throttling.timezone.now", return_value=self.now + COOLDOWN
        ):
            self.assertNotContains(self.client.get(self.login), 'id="login-cooldown"')
            self.client.post(self.login, {"username": "Casey", "password": PASSWORD})
            self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)
            self.assertFalse(LoginFailure.objects.filter(pk=row.pk).exists())

    def test_success_before_the_limit_resets_the_counter(self):
        self.seed("Casey", 4)
        self.client.post(self.login, {"username": "Casey", "password": PASSWORD})
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)
        self.assertFalse(LoginFailure.objects.exists())

    def test_partial_failures_expire_and_empty_fields_do_not_consume_an_attempt(self):
        expired = self.seed("Casey", 4, self.now - timedelta(seconds=1))
        self.seed("unused", 2, self.now - timedelta(days=1))
        self.client.post(self.login, {"username": "Casey", "password": ""})
        expired.refresh_from_db()
        self.assertEqual(expired.failures, 4)
        result = self.client.post(
            self.login, {"username": "Casey", "password": "incorrect fixture"}
        )
        self.assertEqual(result.status_code, 200)
        expired.refresh_from_db()
        self.assertEqual(expired.failures, 1)
        self.assertEqual(LoginFailure.objects.count(), 1)

    def test_unregistered_name_gets_the_same_cooldown(self):
        self.seed("VisitorFixture", 4)
        with patch("accounts.throttling.timezone.now", return_value=self.now):
            response = self.client.post(
                self.login,
                {"username": "visitorfixture", "password": "incorrect fixture"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "120")


@skipUnlessDBFeature("has_select_for_update")
class LoginCounterConcurrencyTests(TransactionTestCase):
    def test_workers_share_one_threshold(self):
        row = LoginFailure.objects.create(
            identity=_identity("counter-fixture"),
            failures=3,
            expires_at=timezone.now() + FAILURE_RETENTION,
        )
        start = Barrier(2)

        def record_fixture_failure():
            try:
                form = LoginForm(
                    request=SimpleNamespace(session={}),
                    data={"username": "counter-fixture", "password": "fixture"},
                )
                start.wait(timeout=5)
                return form.errors.as_data()["__all__"][0].code
            finally:
                connections.close_all()

        rejection = ValidationError("Fixture rejection", code="invalid_login")
        with patch(
            "django.contrib.auth.forms.AuthenticationForm.clean", side_effect=rejection
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                workers = [pool.submit(record_fixture_failure) for _ in range(2)]
                outcomes = [worker.result(timeout=10) for worker in workers]
        self.assertCountEqual(outcomes, ["invalid_login", "cooldown"])
        row.refresh_from_db()
        self.assertEqual(row.failures, 5)
