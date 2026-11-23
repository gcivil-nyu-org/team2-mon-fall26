import os
import runpy
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.tests import PASSWORD, make_user

from . import settings as project_settings


class HTTPSDeploymentTests(TestCase):
    def https_settings(self, enabled):
        environment = {
            "DJANGO_ENFORCE_HTTPS": "1" if enabled else "0",
            "DJANGO_BEHIND_HTTPS_PROXY": "1" if enabled else "0",
            "DJANGO_SECURE_COOKIES": "0",
        }
        with patch.dict(os.environ, environment):
            config = runpy.run_path(project_settings.__file__)
        names = (
            "SECURE_SSL_REDIRECT",
            "SECURE_REDIRECT_EXEMPT",
            "SECURE_HSTS_SECONDS",
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SECURE_PROXY_SSL_HEADER",
        )
        return self.settings(**{name: config.get(name) for name in names})

    def test_redirect_preserves_login_destination_and_http_health_probe_stays_up(self):
        with self.https_settings(enabled=True):
            page = self.client.get("/accounts/login/?next=/forum/")
            self.assertEqual(page.status_code, 301)
            self.assertEqual(
                page.url, "https://testserver/accounts/login/?next=/forum/"
            )
            for probe in (self.client.get, self.client.head):
                health = probe(reverse("health"))
                self.assertEqual(health.status_code, 200)
                self.assertFalse(health.cookies)

    def test_proxy_https_enables_hsts_and_secures_both_authentication_cookies(self):
        make_user("ProxyFixture")
        with self.https_settings(enabled=True):
            headers = {"HTTP_X_FORWARDED_PROTO": "https"}
            login = self.client.get(reverse("accounts:login"), **headers)
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login["Strict-Transport-Security"], "max-age=3600")
            self.assertTrue(login.cookies["csrftoken"]["secure"])
            signed_in = self.client.post(
                reverse("accounts:login"),
                {"username": "ProxyFixture", "password": PASSWORD},
                **headers
            )
            self.assertEqual(signed_in.status_code, 302)
            self.assertTrue(signed_in.cookies["sessionid"]["secure"])
            self.assertTrue(signed_in.cookies["sessionid"]["httponly"])

    def test_local_http_login_page_is_available(self):
        with self.https_settings(enabled=False):
            page = self.client.get(reverse("accounts:login"))
            self.assertEqual(page.status_code, 200)
            self.assertFalse(page.cookies["csrftoken"]["secure"])
            self.assertNotIn("Strict-Transport-Security", page)
