from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rrhh.auditoria"
    verbose_name = "Auditoría"

    def ready(self):
        # Importar signals al arrancar
        import rrhh.auditoria.signals  # noqa