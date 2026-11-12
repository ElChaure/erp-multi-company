"""
Admin de documentos emitidos.
"""

from django.contrib import admin
from .models import DocumentoEmitido


@admin.register(DocumentoEmitido)
class DocumentoEmitidoAdmin(admin.ModelAdmin):
    list_display = [
        "numero_control",
        "tipo",
        "empleado_numero",
        "empleado_nombre",
        "anio",
        "emitido_por",
        "emitido_at",
        "descargas",
    ]
    list_filter = ["tipo", "anio", "empresa"]
    search_fields = [
        "numero_control",
        "empleado__numero_empleado",
        "empleado__nombre",
        "empleado__apellido_paterno",
        "empleado__cedula",
    ]
    readonly_fields = [
        "numero_control",
        "tipo",
        "anio",
        "empleado",
        "empresa",
        "emitido_por",
        "emitido_at",
        "parametros",
        "descargas",
        "ultima_descarga",
    ]
    date_hierarchy = "emitido_at"
    ordering = ["-emitido_at"]

    def has_add_permission(self, request):
        # Solo se crean desde las vistas
        return False

    def has_change_permission(self, request, obj=None):
        # Read-only
        return False

    @admin.display(description="N° empleado", ordering="empleado__numero_empleado")
    def empleado_numero(self, obj):
        return obj.empleado.numero_empleado

    @admin.display(description="Empleado", ordering="empleado__apellido_paterno")
    def empleado_nombre(self, obj):
        return obj.empleado.nombre_completo