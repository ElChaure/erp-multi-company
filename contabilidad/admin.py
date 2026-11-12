from django.contrib import admin
from .models import (
    EjercicioFiscal, PeriodoContable, PlanCuenta,
    CentroCosto, Asiento, AsientoLinea, SaldoCuenta,
    ConfiguracionContableNomina, Presupuesto, PresupuestoLinea,
    ConfiguracionContableCostos,
    ConfiguracionCIF, CentroCostoCIF,
    ConfiguracionIVA, FacturaFiscal, FacturaFiscalLinea,
)


class PeriodoInline(admin.TabularInline):
    model = PeriodoContable
    extra = 0


@admin.register(EjercicioFiscal)
class EjercicioFiscalAdmin(admin.ModelAdmin):
    list_display = ("empresa", "anio", "fecha_inicio", "fecha_fin", "cerrado")
    list_filter = ("empresa", "anio", "cerrado")
    inlines = [PeriodoInline]


@admin.register(PlanCuenta)
class PlanCuentaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "tipo", "naturaleza", "es_agrupadora", "activa", "es_cuenta_de_costo")
    list_filter = ("empresa", "tipo", "naturaleza", "activa", "es_cuenta_de_costo")
    search_fields = ("codigo", "nombre")
    list_editable = ("activa", "es_cuenta_de_costo")


@admin.register(CentroCosto)
class CentroCostoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "tipo", "activo", "capacidad_horas_mes")
    list_filter = ("empresa", "tipo", "activo")
    search_fields = ("codigo", "nombre")


class AsientoLineaInline(admin.TabularInline):
    model = AsientoLinea
    extra = 1
    autocomplete_fields = ["cuenta", "centro_costo"]


@admin.register(Asiento)
class AsientoAdmin(admin.ModelAdmin):
    list_display = ("numero", "empresa", "fecha", "concepto", "total_debito", "total_credito", "estado", "origen_modulo")
    list_filter = ("empresa", "estado", "origen_modulo", "periodo")
    search_fields = ("numero", "concepto")
    inlines = [AsientoLineaInline]
    readonly_fields = ("total_debito", "total_credito")


@admin.register(SaldoCuenta)
class SaldoCuentaAdmin(admin.ModelAdmin):
    list_display = ("cuenta", "periodo", "centro_costo", "saldo_inicial", "debitos_periodo", "creditos_periodo", "saldo_final")
    list_filter = ("periodo", "cuenta")
    search_fields = ("cuenta__codigo", "cuenta__nombre")
    readonly_fields = ("saldo_inicial", "debitos_periodo", "creditos_periodo", "saldo_final", "actualizado_at")


@admin.register(ConfiguracionContableNomina)
class ConfiguracionContableNominaAdmin(admin.ModelAdmin):
    list_display = ("empresa", "concepto", "cuenta", "cuenta_pasivo")
    list_filter = ("empresa",)
    search_fields = ("concepto__codigo", "concepto__nombre", "cuenta__codigo")
    autocomplete_fields = ["concepto", "cuenta", "cuenta_pasivo"]


@admin.register(ConfiguracionContableCostos)
class ConfiguracionContableCostosAdmin(admin.ModelAdmin):
    list_display = (
        "empresa",
        "cuenta_inventario_pt",
        "cuenta_costo_mp",
        "cuenta_costo_mod",
        "cuenta_costo_cif",
        "cuenta_sueldos_por_pagar",
        "actualizado_at",
    )
    list_filter = ("empresa",)
    search_fields = ("empresa__razon_social",)
    autocomplete_fields = [
        "cuenta_inventario_pt",
        "cuenta_costo_mp",
        "cuenta_costo_mod",
        "cuenta_costo_cif",
        "cuenta_sueldos_por_pagar",
    ]
    fieldsets = (
        ("Empresa", {"fields": ("empresa",)}),
        ("Inventario", {
            "fields": ("cuenta_inventario_pt",),
            "description": "Cuenta de activo donde se acumula el inventario al costear una orden.",
        }),
        ("Costos de producción (MP / MOD / CIF)", {
            "fields": ("cuenta_costo_mp", "cuenta_costo_mod", "cuenta_costo_cif"),
            "description": (
                "Cuentas de <b>movimiento</b>. "
                "Default: <b>5101</b> (MP), <b>5102</b> (MOD), <b>5103</b> (CIF)."
            ),
        }),
        ("Nómina", {
            "fields": ("cuenta_sueldos_por_pagar",),
            "description": "Cuenta de pasivo. Default: <b>210102</b>.",
        }),
    )
    readonly_fields = ("actualizado_at",)


# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE REPARTO DE CIF  (Sprint 2.5)
# ═══════════════════════════════════════════════════════════

class CentroCostoCIFInline(admin.TabularInline):
    model = CentroCostoCIF
    extra = 1
    autocomplete_fields = ["centro_costo"]
    readonly_fields = ("coeficiente_calculado",)
    fields = (
        "centro_costo",
        "area_cm2",
        "horas_maquina_mes",
        "horas_hombre_mes",
        "unidades_mes",
        "costo_directo_mes",
        "coeficiente_manual",
        "coeficiente_calculado",
    )


@admin.register(ConfiguracionCIF)
class ConfiguracionCIFAdmin(admin.ModelAdmin):
    list_display = (
        "empresa",
        "driver",
        "centro_pivot",
        "base_pivot",
        "metodo",
        "activa",
        "actualizado_at",
    )
    list_filter = ("driver", "metodo", "activa", "empresa")
    search_fields = ("empresa__razon_social",)
    autocomplete_fields = ["centro_pivot"]
    inlines = [CentroCostoCIFInline]
    readonly_fields = ("actualizado_at",)
    fieldsets = (
        ("Empresa", {"fields": ("empresa",)}),
        ("Driver y base de reparto", {
            "fields": ("driver", "centro_pivot", "base_pivot", "metodo"),
            "description": (
                "El <b>pivot</b> es el centro de costo de referencia (coeficiente = 1). "
                "La <b>base del pivot</b> es el valor del driver para ese centro. "
                "El coeficiente de cada CC se calcula como "
                "<code>driver_cc / base_pivot</code>."
            ),
        }),
        ("Estado", {"fields": ("activa", "notas")}),
        ("Auditoría", {"fields": ("actualizado_at",), "classes": ("collapse",)}),
    )


@admin.register(CentroCostoCIF)
class CentroCostoCIFAdmin(admin.ModelAdmin):
    list_display = (
        "configuracion",
        "centro_costo",
        "coeficiente_calculado",
    )
    list_filter = ("configuracion__empresa", "configuracion__driver")
    search_fields = ("centro_costo__codigo", "centro_costo__nombre")
    autocomplete_fields = ["configuracion", "centro_costo"]
    readonly_fields = ("coeficiente_calculado", "actualizado_at")


# ═══════════════════════════════════════════════════════════
#  PRESUPUESTO (Fase 3)
# ═══════════════════════════════════════════════════════════

class PresupuestoLineaInline(admin.TabularInline):
    model = PresupuestoLinea
    extra = 1
    autocomplete_fields = ["cuenta", "centro_costo"]
    fields = [
        "cuenta", "centro_costo",
        "monto_enero", "monto_febrero", "monto_marzo", "monto_abril",
        "monto_mayo", "monto_junio", "monto_julio", "monto_agosto",
        "monto_septiembre", "monto_octubre", "monto_noviembre", "monto_diciembre",
    ]


@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "ejercicio", "activo")
    list_filter = ("empresa", "ejercicio", "activo")
    search_fields = ("nombre",)
    inlines = [PresupuestoLineaInline]


@admin.register(PresupuestoLinea)
class PresupuestoLineaAdmin(admin.ModelAdmin):
    list_display = ("presupuesto", "cuenta", "centro_costo")
    list_filter = ("presupuesto__empresa", "presupuesto__ejercicio")
    search_fields = ("cuenta__codigo", "cuenta__nombre")
    autocomplete_fields = ["cuenta", "centro_costo"]


# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE IVA Y FACTURAS FISCALES  (Sprint 3)
# ═══════════════════════════════════════════════════════════

@admin.register(ConfiguracionIVA)
class ConfiguracionIVAAdmin(admin.ModelAdmin):
    list_display = (
        "empresa",
        "alicuota_general",
        "alicuota_reducida",
        "contribuyente_especial",
        "rif",
        "activa",
        "actualizado_at",
    )
    list_filter = ("empresa", "contribuyente_especial", "activa")
    search_fields = ("empresa__razon_social", "rif")
    readonly_fields = ("actualizado_at",)
    fieldsets = (
        ("Empresa", {"fields": ("empresa",)}),
        ("Alícuotas de IVA", {
            "fields": ("alicuota_general", "alicuota_reducida"),
            "description": "Alícuota general (default 16%) y reducida (default 8%).",
        }),
        ("Datos fiscales", {
            "fields": ("contribuyente_especial", "rif", "razon_social"),
            "description": "Si es contribuyente especial, está sujeto a retenciones de IVA.",
        }),
        ("Estado", {"fields": ("activa",)}),
    )


class FacturaFiscalLineaInline(admin.TabularInline):
    model = FacturaFiscalLinea
    extra = 1
    fields = (
        "descripcion", "cantidad", "precio_unitario",
        "base_imponible", "alicuota_iva", "monto_iva", "monto_total",
    )
    readonly_fields = ("base_imponible", "monto_iva", "monto_total")


@admin.register(FacturaFiscal)
class FacturaFiscalAdmin(admin.ModelAdmin):
    list_display = (
        "numero_factura",
        "numero_control",
        "tipo",
        "fecha_emision",
        "rif_contraparte",
        "razon_social_contraparte",
        "base_imponible",
        "monto_iva",
        "monto_total",
        "estado",
    )
    list_filter = (
        "empresa", "tipo", "estado", "fecha_emision",
        "tipo_transaccion", "alicuota_iva",
    )
    search_fields = (
        "numero_factura", "numero_control",
        "rif_contraparte", "razon_social_contraparte",
    )
    date_hierarchy = "fecha_emision"
    autocomplete_fields = ["asiento", "factura_origen"]
    inlines = [FacturaFiscalLineaInline]
    readonly_fields = ("creado_at", "actualizado_at")
    fieldsets = (
        ("Empresa y tipo", {
            "fields": ("empresa", "tipo", "estado", "tipo_transaccion"),
        }),
        ("Datos del documento", {
            "fields": (
                "numero_factura", "numero_control",
                "fecha_emision", "fecha_vencimiento",
            ),
        }),
        ("Contraparte", {
            "fields": (
                "rif_contraparte", "razon_social_contraparte", "direccion_contraparte",
            ),
        }),
        ("Montos", {
            "fields": (
                "base_imponible", "alicuota_iva", "monto_iva",
                "monto_exento", "monto_total",
            ),
        }),
        ("Retenciones", {
            "fields": ("iva_retenido", "numero_comprobante_retencion"),
            "classes": ("collapse",),
        }),
        ("Vínculo contable", {
            "fields": ("asiento", "factura_origen"),
        }),
        ("Auditoría", {
            "fields": ("observaciones", "creado_por", "creado_at", "actualizado_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(FacturaFiscalLinea)
class FacturaFiscalLineaAdmin(admin.ModelAdmin):
    list_display = (
        "factura", "descripcion", "cantidad", "precio_unitario",
        "base_imponible", "alicuota_iva", "monto_iva", "monto_total",
    )
    list_filter = ("factura__empresa", "factura__tipo")
    search_fields = ("descripcion", "factura__numero_factura")
    autocomplete_fields = ["factura"]