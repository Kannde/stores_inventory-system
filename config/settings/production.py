from .base import *


DEBUG = False
DATABASES = database_config()
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "example.com,www.example.com")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://example.com,https://www.example.com",
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(["whitenoise.middleware.WhiteNoiseMiddleware"] if WHITENOISE_INSTALLED else []),
    *MIDDLEWARE[1:],
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", True)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
