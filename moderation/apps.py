from django.apps import AppConfig


class ModerationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "moderation"
    verbose_name = "Community moderation"

    def ready(self):
        from . import registry, signals

        signals.connect(registry.all_types())
