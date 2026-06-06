from django.apps import AppConfig

class CustomrequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'custom_services'

    def ready(self):
        import custom_services.tasks  # noqa