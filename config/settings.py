"""Connect NYC: one Django application backed by MySQL."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "replace-with-a-random-secret":
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY; run python3 scripts/create_env.py for a local demo.")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]
DEMO_MODE = os.environ.get("DEMO_MODE", "0") == "1"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "hotspots.apps.HotspotsConfig",
    "reviews.apps.ReviewsConfig",
    "accounts.apps.AccountsConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "accounts.context_processors.roles",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": os.environ.get("MYSQL_DATABASE", "connectnyc"),
    "USER": os.environ.get("MYSQL_USER", "connectnyc"),
    "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
    "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "PORT": os.environ.get("MYSQL_PORT", "3306"),
    "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    "CONN_MAX_AGE": 60,
    "CONN_HEALTH_CHECKS": True,
}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
# E02 account access. Django stores salted PBKDF2-SHA256 password hashes, never plain text.
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "hotspots:map"
LOGOUT_REDIRECT_URL = "hotspots:map"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MAP_TILE_URL = os.environ.get("MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
MAP_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# Send the origin on cross-origin tile requests, as required by the tile provider.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
# Enable these behind HTTPS on AWS; the local demo uses HTTP on loopback only.
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "0") == "1"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
# Behind an HTTPS load balancer (e.g. AWS), list the public origin(s) so login and
# sign-up forms pass CSRF checks, and trust the proxy's X-Forwarded-Proto header.
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
if os.environ.get("DJANGO_BEHIND_HTTPS_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
