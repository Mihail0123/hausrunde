from django.apps import AppConfig


class AdsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.ads"

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401
