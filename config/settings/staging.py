from .base import *


DEBUG = False
DATABASES = database_config()
ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "staging.localhost,127.0.0.1,localhost",
)
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000,https://staging.example.com",
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(["whitenoise.middleware.WhiteNoiseMiddleware"] if WHITENOISE_INSTALLED else []),
    *MIDDLEWARE[1:],
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
