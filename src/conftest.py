import pytest
from django.core.cache import caches
from django.conf import settings

@pytest.fixture(autouse=True)
def clear_all_caches():
    """Reset throttle history and any per-site cache before every test."""
    for alias in settings.CACHES.keys():
        caches[alias].clear()
