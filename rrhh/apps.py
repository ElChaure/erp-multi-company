from django.apps import AppConfig


class RrhhConfig(AppConfig):
    name = 'rrhh'
    verbose_name = "RRHH"

    def ready(self):
        # Importar signals al arrancar la app
        import rrhh.ausencias.signals