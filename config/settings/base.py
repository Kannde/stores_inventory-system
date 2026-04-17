import os
from importlib.util import find_spec
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def env(key, default=None):
    return os.getenv(key, default)


def env_bool(key, default=False):
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key, default=""):
    value = os.getenv(key)
    if value is None:
        value = default
    return [item.strip() for item in value.split(",") if item.strip()]


def database_config(*, default_sqlite=False):
    db_engine = env("DB_ENGINE")

    if not db_engine and default_sqlite:
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

    return {
        "default": {
            "ENGINE": db_engine or "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "stores_inventory_system"),
            "USER": env("DB_USER", "postgres"),
            "PASSWORD": env("DB_PASSWORD", "postgres"),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
        }
    }


WHITENOISE_INSTALLED = find_spec("whitenoise") is not None

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    env(
        "SECRET_KEY",
        "django-insecure-change-me-before-exposing-this-project",
    ),
)

DEBUG = env_bool("DJANGO_DEBUG", env_bool("DEBUG", False))
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    env("ALLOWED_HOSTS", "127.0.0.1,localhost"),
)
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    env(
        "CSRF_TRUSTED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ),
)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "inventory",
    "sales",
    "preorders",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", env("LANGUAGE_CODE", "en-us"))
TIME_ZONE = env("DJANGO_TIME_ZONE", env("TIME_ZONE", "UTC"))
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SUPERUSER_USERNAME = env("DJANGO_SUPERUSER_USERNAME", "kannde")
SUPERUSER_EMAIL = env("DJANGO_SUPERUSER_EMAIL", "kannde@example.com")
SUPERUSER_PASSWORD = env("DJANGO_SUPERUSER_PASSWORD", "Test@12345")
