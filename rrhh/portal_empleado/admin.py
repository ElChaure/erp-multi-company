"""
Admin del Portal del Empleado.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import CuentaEmpleado


@admin.register(CuentaEmpleado)
class CuentaEmpleadoAdmin(admin.ModelAdmin):
    list_display = [
        "empleado_numero",
        "empleado_nombre",
        "username",
        "activo",
        "email_verificado",
        "ultimo_login",
        "fecha_creacion",
    ]
    list_filter = ["activo", "email_verificado"]
    search_fields = [
        "empleado__numero_empleado",
        "empleado__nombre",
        "empleado__apellido_paterno",
        "empleado__cedula",
        "usuario__username",
        "usuario__email",
    ]
    readonly_fields = [
        "usuario",
        "empleado",
        "ultimo_login",
        "ultimo_login_ip",
        "fecha_creacion",
        "fecha_actualizacion",
    ]
    autocomplete_fields = ["empleado"]
    fieldsets = [
        ("Vinculación", {
            "fields": ["empleado", "usuario"],
        }),
        ("Estado", {
            "fields": ["activo", "email_verificado"],
        }),
        ("Actividad", {
            "fields": ["ultimo_login", "ultimo_login_ip"],
        }),
        ("Auditoría", {
            "fields": ["creado_por", "fecha_creacion", "fecha_actualizacion"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Nº empleado", ordering="empleado__numero_empleado")
    def empleado_numero(self, obj):
        return obj.empleado.numero_empleado

    @admin.display(description="Empleado", ordering="empleado__apellido_paterno")
    def empleado_nombre(self, obj):
        return obj.empleado.nombre_completo

    @admin.display(description="Usuario")
    def username(self, obj):
        return obj.usuario.username