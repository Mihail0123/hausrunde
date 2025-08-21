# Test settings override: isolate caches, keep throttling exactly as in base settings.
from .settings import *  # noqa

# In-memory cache to avoid cross-test pollution (throttle history, etc.)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
        "TIMEOUT": 0,
        "KEY_PREFIX": "tests",
    }
}
CACHE_MIDDLEWARE_SECONDS = 0
CACHE_MIDDLEWARE_KEY_PREFIX = "tests"

# Speed up tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# IMPORTANT:
# Do NOT override REST_FRAMEWORK here.
# Throttling classes/rates stay exactly as in base settings.
