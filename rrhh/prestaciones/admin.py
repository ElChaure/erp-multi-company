"""
Admin del módulo de prestaciones.
"""
from django.contrib import admin
from django.db.models import Count, Sum

from .models import (
    ConfiguracionPrestaciones,
    PrestacionSocial,
    DepositoPrestacion,
    CalculoRetroactivo,
    TasaInteresPrestaciones,
)


@admin.register(ConfiguracionPrestaciones)
class ConfiguracionPrestacionesAdmin(admin.ModelAdmin):
    list_display = ["empresa", "modo_calculo", "frecuencia_deposito",
                    "tipo_acreditacion", "maneja_doble_moneda", "activa"]
    list_filter = ["modo_calculo", "frecuencia_deposito",
                   "tipo_acreditacion", "activa", "maneja_doble_moneda"]
    search_fields = ["empresa__razon_social", "empresa__rif"]
    autocomplete_fields = ["empresa", "banco_fideicomiso"]


class DepositoPrestacionInline(admin.TabularInline):
    model = DepositoPrestacion
    extra = 0
    fields = ["anio", "trimestre", "dias_garantia", "dias_adicionales",
              "salario_integral_diario_ves", "monto_ves", "estatus"]
    readonly_fields = ["salario_integral_diario_ves"]
    ordering = ["-anio", "-trimestre"]


@admin.register(PrestacionSocial)
class PrestacionSocialAdmin(admin.ModelAdmin):
    list_display = ["empleado", "fecha_inicio", "saldo_total_ves",
                    "ultimo_retroactivo", "ultimo_metodo_aplicado", "estatus"]
    list_filter = ["estatus", "ultimo_metodo_aplicado"]
    search_fields = ["empleado__nombre", "empleado__apellido_paterno",
                     "empleado__numero_empleado", "empleado__cedula"]
    autocomplete_fields = ["empleado"]
    inlines = [DepositoPrestacionInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DepositoPrestacion)
class DepositoPrestacionAdmin(admin.ModelAdmin):
    list_display = ["prestacion", "anio", "trimestre", "dias_garantia",
                    "dias_adicionales", "monto_ves", "estatus"]
    list_filter = ["estatus", "anio", "trimestre"]
    search_fields = ["prestacion__empleado__nombre",
                     "prestacion__empleado__apellido_paterno",
                     "prestacion__empleado__numero_empleado"]
    autocomplete_fields = ["prestacion"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CalculoRetroactivo)
class CalculoRetroactivoAdmin(admin.ModelAdmin):
    list_display = ["prestacion", "fecha_corte", "anios_servicio",
                    "monto_retroactivo_ves", "saldo_garantia_ves",
                    "metodo_seleccionado", "monto_final_ves"]
    list_filter = ["metodo_seleccionado", "fecha_corte"]
    search_fields = ["prestacion__empleado__nombre",
                     "prestacion__empleado__apellido_paterno"]
    autocomplete_fields = ["prestacion"]
    readonly_fields = ["fecha_calculo"]


@admin.register(TasaInteresPrestaciones)
class TasaInteresPrestacionesAdmin(admin.ModelAdmin):
    list_display = ["empresa", "anio", "mes", "moneda",
                    "tasa_anual_pct", "fuente", "created_at"]
    list_filter = ["empresa", "anio", "moneda", "fuente"]
    search_fields = ["empresa__razon_social"]
    autocomplete_fields = ["empresa"]
    ordering = ["-anio", "-mes"]