from django.apps import AppConfig


class PortalEmpleadoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rrhh.portal_empleado"
    verbose_name = "Portal del Empleado (API)"
    label = "rrhh_portal_empleado"