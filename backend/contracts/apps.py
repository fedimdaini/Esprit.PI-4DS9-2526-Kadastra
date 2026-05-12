from django.apps import AppConfig


class ContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contracts'
    verbose_name = 'Contrats NLP'

    def ready(self):
        """Initialize NLP models at server startup (not per-request)."""
        # Import here to trigger lazy loading setup
        pass
