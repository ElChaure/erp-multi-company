from django.contrib import admin
from .models import ActivoFijo, DepreciacionActivo


class DepreciacionInline(admin.TabularInline):
    model = DepreciacionActivo
    extra = 0
    readonly_fields = ("fecha", "monto", "asiento")
    can_delete = False


@admin.register(ActivoFijo)
class ActivoFijoAdmin(admin.ModelAdmin):
    # ---- LISTADO (columnas calculadas aquí) ----
    list_display = (
        "codigo", "nombre", "empresa",
        "costo_adquisicion", "valor_residual", "base_depreciable_calc",
        "vida_util_anios", "depreciacion_mensual_calc", "valor_libro_calc",
        "metodo_depreciacion", "activo"
    )
    list_filter = ("empresa", "metodo_depreciacion", "activo")
    search_fields = ("codigo", "nombre", "serial")
    autocomplete_fields = [
        "cuenta_activo", "cuenta_gasto_depreciacion",
        "cuenta_depreciacion_acumulada", "centro_costo"
    ]
    inlines = [DepreciacionInline]

    # ---- FORMULARIO (solo campos editables) ----
    fieldsets = (
        ("Identificación", {
            "fields": ("empresa", "sede", "centro_costo", "codigo", "nombre", "descripcion", "serial")
        }),
        ("Fechas y Valores", {
            "fields": (
                "fecha_adquisicion", "fecha_inicio_depreciacion",
                "costo_adquisicion", "valor_residual", "vida_util_anios",
            )
        }),
        ("Método de Depreciación", {
            "fields": ("metodo_depreciacion", "tasa_anual", "total_unidades_estimadas")
        }),
        ("Cuentas Contables", {
            "fields": ("cuenta_activo", "cuenta_gasto_depreciacion", "cuenta_depreciacion_acumulada")
        }),
        ("Estado", {
            "fields": ("activo",)
        }),
    )

    # ---- MÉTODOS PARA EL LISTADO ----
    def base_depreciable_calc(self, obj):
        return f"Bs. {obj.base_depreciable:,.2f}"
    base_depreciable_calc.short_description = "Base Depreciable"
    base_depreciable_calc.admin_order_field = "costo_adquisicion"  # permite ordenar

    def depreciacion_mensual_calc(self, obj):
        return f"Bs. {obj.depreciacion_mensual:,.2f}"
    depreciacion_mensual_calc.short_description = "Dep. Mensual"

    def valor_libro_calc(self, obj):
        return f"Bs. {obj.valor_libro:,.2f}"
    valor_libro_calc.short_description = "Valor Libro"