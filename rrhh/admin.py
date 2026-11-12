from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponse
from django.db.models import Count
from django.utils.safestring import mark_safe

from .models import (
    # Core
    Empresa, Sede, Cargo, Departamento,
    # Empleado
    Empleado, Perfil,
    # Nómina
    ParametroNomina, ConceptoNomina, PeriodoNomina,
    NominaEmpleado, NominaDetalle, IncidenciaNomina,
    TipoAusencia, SaldoVacaciones, SolicitudAusencia, MovimientoSaldoVacaciones,
    Banco,ConfiguracionVacaciones, VacacionColectiva,
)


# ═══════════════════════════════════════════════════════════
#  EMPRESA
# ═══════════════════════════════════════════════════════════

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = (
        "rif",
        "razon_social",
        "tipo",
        "padre",
        "moneda",
        "activa",
        "tiene_firma_y_sello",
    )
    list_filter = ("tipo", "activa", "pais", "moneda")
    search_fields = ("rif", "razon_social", "nombre_comercial")
    autocomplete_fields = ("padre",)
    list_per_page = 25

    fieldsets = (
        ("Identificación", {
            "fields": (
                "tipo",
                "padre",
                "rif",
                "razon_social",
                "nombre_comercial",
            )
        }),
        ("Contacto", {
            "fields": (
                "telefono",
                "email",
                "sitio_web",
            )
        }),
        ("Dirección fiscal", {
            "fields": (
                "direccion",
                "ciudad",
                "estado",
                "pais",
            )
        }),
        ("Configuración", {
            "fields": (
                "moneda",
                "zona_horaria",
                "logo",
                "activa",
            )
        }),
        ("Documentos formales (firma y sello)", {
            "fields": (
                "nombre_agente_retencion",
                "cargo_agente_retencion",
                "firma_agente_retencion",
                "preview_firma",
                "sello_empresa",
                "preview_sello",
            ),
            "description": (
                "Estos datos se usan en la <strong>Constancia de Trabajo</strong> "
                "y en la <strong>Planilla ARC</strong>. "
                "Las imágenes deben ser <strong>PNG con fondo transparente</strong>. "
                "Tamaño recomendado: firma 400x120 px, sello 300x300 px."
            ),
        }),
    )

    readonly_fields = (
        "preview_firma",
        "preview_sello",
    )

    # ═══════════════════════════════════════════════════════
    #  PREVIEWS DE FIRMA Y SELLO
    # ═══════════════════════════════════════════════════════

    @admin.display(description="Vista previa de la firma")
    def preview_firma(self, obj):
        if not obj or not obj.firma_agente_retencion:
            return mark_safe(
                '<span style="color: #9ca3af; font-style: italic;">'
                'Aún no se ha subido una firma</span>'
            )
        return format_html(
            '<div style="background: #f9fafb; border: 1px dashed #d1d5db; '
            'border-radius: 6px; padding: 15px; text-align: center; '
            'max-width: 350px;">'
            '<img src="{}" style="max-height: 100px; max-width: 300px;" />'
            '</div>',
            obj.firma_agente_retencion.url,
        )

    @admin.display(description="Vista previa del sello")
    def preview_sello(self, obj):
        if not obj or not obj.sello_empresa:
            return mark_safe(
                '<span style="color: #9ca3af; font-style: italic;">'
                'Aún no se ha subido un sello</span>'
            )
        return format_html(
            '<div style="background: #f9fafb; border: 1px dashed #d1d5db; '
            'border-radius: 6px; padding: 15px; text-align: center; '
            'max-width: 350px;">'
            '<img src="{}" style="max-height: 150px; max-width: 250px;" />'
            '</div>',
            obj.sello_empresa.url,
        )

    # ═══════════════════════════════════════════════════════
    #  INDICADOR EN LA LISTA
    # ═══════════════════════════════════════════════════════

    @admin.display(description="Firma/Sello", boolean=True)
    def tiene_firma_y_sello(self, obj):
        return bool(obj.firma_agente_retencion and obj.sello_empresa)
        
# ═══════════════════════════════════════════════════════════
#  SEDE
# ═══════════════════════════════════════════════════════════

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "empresa",
        "tipo",
        "es_principal",
        "ciudad",
        "activa",
    )
    list_filter = ("tipo", "es_principal", "activa", "empresa")
    search_fields = ("codigo", "nombre", "empresa__razon_social")
    autocomplete_fields = ("empresa",)
    list_per_page = 25

    fieldsets = (
        ("Ubicación organizacional", {
            "fields": (
                "empresa",
                "tipo",
                "es_principal",
            )
        }),
        ("Identificación", {
            "fields": (
                "codigo",
                "nombre",
            )
        }),
        ("Dirección", {
            "fields": (
                "direccion",
                "ciudad",
                "estado",
                "pais",
                "codigo_postal",
            )
        }),
        ("Contacto", {
            "fields": (
                "telefono",
                "email",
            )
        }),
        ("Estado", {
            "fields": ("activa",)
        }),
    )


# ═══════════════════════════════════════════════════════════
#  CARGO
# ═══════════════════════════════════════════════════════════

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "salario_min",
        "salario_max",
        "activo",
    )
    list_filter = ("activo",)
    search_fields = ("codigo", "nombre")
    ordering = ("nombre",)
    list_per_page = 25


# ═══════════════════════════════════════════════════════════
#  DEPARTAMENTO
# ═══════════════════════════════════════════════════════════

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "empresa",
        "padre",
        "presupuesto_anual",
        "activo",
    )
    list_filter = ("activo", "empresa")
    search_fields = ("codigo", "nombre")
    autocomplete_fields = ("empresa", "padre", "responsable")
    list_per_page = 25

# ═══════════════════════════════════════════════════════════
#  BANCO
# ═══════════════════════════════════════════════════════════

@admin.register(Banco)
class BancoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "nombre_corto", "activo", "empleados_count"]
    list_filter = ["activo"]
    search_fields = ["codigo", "nombre", "nombre_corto"]
    ordering = ["codigo"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = [
        ("Identificación", {
            "fields": ["codigo", "nombre", "nombre_corto"],
        }),
        ("Estado", {
            "fields": ["activo"],
        }),
        ("Auditoría", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _empleados_count=Count("empleados")
        )

    @admin.display(description="Empleados", ordering="_empleados_count")
    def empleados_count(self, obj):
        return obj.empleados.count()

# ═══════════════════════════════════════════════════════════
#  EMPLEADO
# ═══════════════════════════════════════════════════════════

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = (
        "numero_empleado",
        "nombre_completo_display",
        "cedula_display",
        "empresa",
        "cargo",
        "estatus",
    )
    list_filter = (
        "empresa",
        "estatus",
        "nacionalidad",
        "tipo_contrato",
        "cargo",
    )
    search_fields = (
        "numero_empleado",
        "nombre",
        "apellido_paterno",
        "apellido_materno",
        "cedula",
        "email",
    )
    autocomplete_fields = (
        "empresa",
        "sede",
        "cargo",
        "departamento",
        "jefe",
        "banco",
    )
    date_hierarchy = "fecha_ingreso"
    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    list_per_page = 25

    fieldsets = (
        ("Empresa y sede", {
            "fields": (
                "empresa",
                "sede",
                "numero_empleado",
            )
        }),
        ("Identificación personal", {
            "fields": (
                "nacionalidad",
                "cedula",
            )
        }),
        ("Datos personales", {
            "fields": (
                "nombre",
                "apellido_paterno",
                "apellido_materno",
                "fecha_nacimiento",
                "genero",
                "estado_civil",
            )
        }),
        ("Contacto", {
            "fields": (
                "email",
                "telefono",
                "telefono_habitacion",
                "direccion",
                "ciudad",
                "estado",
                "pais",
            )
        }),
        ("Datos laborales", {
            "fields": (
                "cargo",
                "departamento",
                "jefe",
                "fecha_ingreso",
                "fecha_egreso",
                "tipo_contrato",
                "tipo_jornada",
                "estatus",
                "salario_base",
                "periodicidad_pago",
            )
        }),
        ("Datos bancarios", {
            "fields": (
                "banco",
                "cuenta_bancaria",
                "clabe",
            ),
            "classes": ("collapse",),
        }),
        ("Auditoría", {
            "fields": (
                "created_at",
                "updated_at",
                "created_by",
                "updated_by",
            ),
            "classes": ("collapse",),
        }),
    )

    def nombre_completo_display(self, obj):
        return obj.nombre_completo
    nombre_completo_display.short_description = "Nombre completo"

    def cedula_display(self, obj):
        return obj.cedula_completa
    cedula_display.short_description = "Cédula"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user

        if user.is_superuser:
            return qs

        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(empresa=user.perfil.empresa)

        return qs.none()


# ═══════════════════════════════════════════════════════════
#  PERFIL (inline dentro de User)
# ═══════════════════════════════════════════════════════════

class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = "Perfil"
    autocomplete_fields = ("empresa", "empleado")
    extra = 0

    fieldsets = (
        (None, {
            "fields": (
                "rol",
                "empresa",
                "empleado",
            )
        }),
        ("Información adicional", {
            "fields": (
                "cargo",
                "telefono",
            ),
            "classes": ("collapse",),
        }),
    )


class UserAdmin(BaseUserAdmin):
    inlines = [PerfilInline]
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "get_rol",
        "get_empresa",
        "is_active",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "perfil__rol",
        "perfil__empresa",
    )
    search_fields = ("username", "email", "first_name", "last_name")

    def get_rol(self, obj):
        if hasattr(obj, "perfil"):
            return obj.perfil.get_rol_display()
        return "—"
    get_rol.short_description = "Rol"

    def get_empresa(self, obj):
        if hasattr(obj, "perfil") and obj.perfil.empresa:
            return obj.perfil.empresa.razon_social
        return "— (Global)"
    get_empresa.short_description = "Empresa"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "rol",
        "empresa",
        "cargo",
    )
    list_filter = ("rol", "empresa")
    search_fields = (
        "usuario__username",
        "usuario__email",
        "usuario__first_name",
        "usuario__last_name",
    )
    autocomplete_fields = ("empresa", "empleado")
    list_per_page = 25


# ═══════════════════════════════════════════════════════════
#  PARÁMETROS DE NÓMINA
# ═══════════════════════════════════════════════════════════

@admin.register(ParametroNomina)
class ParametroNominaAdmin(admin.ModelAdmin):
    list_display = (
        "empresa",
        "anio",
        "salario_minimo",
        "unidad_tributaria",
        "tasa_bcv_usd",
        "lopcymat_categoria",
        "activo",
    )
    list_filter = ("anio", "empresa", "activo", "lopcymat_categoria")
    search_fields = ("empresa__razon_social", "anio")
    autocomplete_fields = ("empresa",)
    list_per_page = 20

    fieldsets = (
        ("Identificación", {
            "fields": ("empresa", "anio", "activo")
        }),
        ("Salarios y unidades", {
            "fields": (
                "salario_minimo",
                "cestaticket_mensual_usd",
                "unidad_tributaria",
                "tasa_bcv_usd",
            )
        }),
        ("IVSS", {
            "fields": (
                "ivss_obrero_pct",
                "ivss_patronal_pct",
                "ivss_tope_salarios",
            ),
            "classes": ("collapse",),
        }),
        ("Paro Forzoso (RPE)", {
            "fields": (
                "rpe_obrero_pct",
                "rpe_patronal_pct",
                "rpe_tope_salarios",
            ),
            "classes": ("collapse",),
        }),
        ("BANAVIH", {
            "fields": (
                "banavih_obrero_pct",
                "banavih_patronal_pct",
            ),
            "classes": ("collapse",),
        }),
        ("INCES", {
            "fields": ("inces_patronal_pct",),
            "classes": ("collapse",),
        }),
        ("LOPCYMAT", {
            "fields": ("lopcymat_categoria",),
        }),
        ("Prestaciones sociales", {
            "fields": (
                "dias_prestaciones_trimestre",
                "dias_prestaciones_anio",
                "dias_adicionales_por_anio",
            ),
            "classes": ("collapse",),
        }),
        ("Utilidades y vacaciones", {
            "fields": (
                "dias_utilidades_min",
                "dias_utilidades_max",
                "dias_vacaciones_base",
                "dias_vacaciones_max",
                "dias_bono_vacacional_base",
                "dias_bono_vacacional_max",
                "dias_aguinaldo",
            ),
            "classes": ("collapse",),
        }),
        ("Factor de integración", {
            "fields": ("factor_integracion",),
            "classes": ("collapse",),
        }),
    )


# ═══════════════════════════════════════════════════════════
#  CONCEPTOS DE NÓMINA
# ═══════════════════════════════════════════════════════════

@admin.register(ConceptoNomina)
class ConceptoNominaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "tipo",
        "naturaleza",
        "es_fijo",
        "afecta_isr",
        "afecta_ivss",
        "activo",
    )
    list_filter = (
        "tipo",
        "naturaleza",
        "es_fijo",
        "afecta_isr",
        "afecta_ivss",
        "afecta_rpe",
        "activo",
        "empresa",
    )
    search_fields = ("codigo", "nombre")
    autocomplete_fields = ("empresa",)
    list_per_page = 30
    ordering = ("prioridad", "codigo")

    fieldsets = (
        ("Identificación", {
            "fields": ("empresa", "codigo", "nombre", "descripcion")
        }),
        ("Clasificación", {
            "fields": (
                "tipo",
                "naturaleza",
                "origen",
                "es_fijo",
                "prioridad",
            )
        }),
        ("Fiscalidad", {
            "fields": (
                "forma_parte_salario_normal",
                "afecta_isr",
                "afecta_ivss",
                "afecta_rpe",
                "afecta_banavih",
            )
        }),
        ("Cálculo", {
            "fields": ("formula", "exencion_formula")
        }),
        ("Estado", {
            "fields": ("activo",)
        }),
    )


# ═══════════════════════════════════════════════════════════
#  PERIODOS DE NÓMINA
# ═══════════════════════════════════════════════════════════

class NominaEmpleadoInline(admin.TabularInline):
    model = NominaEmpleado
    extra = 0
    fields = (
        "empleado",
        "dias_trabajados",
        "total_percepciones",
        "total_deducciones",
        "neto_pagar",
        "estatus",
    )
    readonly_fields = (
        "total_percepciones",
        "total_deducciones",
        "neto_pagar",
    )
    can_delete = False
    show_change_link = True
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PeriodoNomina)
class PeriodoNominaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "empresa",
        "tipo",
        "numero_periodo",
        "anio",
        "fecha_inicio",
        "fecha_fin",
        "fecha_pago",
        "estatus_badge",
        "empleados_procesados",
        "total_neto_fmt",
    )
    list_filter = ("estatus", "tipo", "anio", "empresa")
    search_fields = ("empresa__razon_social", "numero_periodo")
    autocomplete_fields = ("empresa",)
    date_hierarchy = "fecha_pago"
    list_per_page = 20
    inlines = [NominaEmpleadoInline]
    actions = ["accion_calcular", "accion_aprobar", "accion_cerrar"]

    fieldsets = (
        ("Identificación", {
            "fields": ("empresa", "tipo", "numero_periodo", "anio")
        }),
        ("Fechas", {
            "fields": ("fecha_inicio", "fecha_fin", "fecha_pago")
        }),
        ("Totales", {
            "fields": (
                "total_percepciones",
                "total_deducciones",
                "total_neto",
                "total_aportes_patronales",
                "total_costo_empresa",
                "empleados_procesados",
            ),
            "classes": ("collapse",),
        }),
        ("Estatus y auditoría", {
            "fields": (
                "estatus",
                "calculado_por", "calculado_at",
                "aprobado_por", "aprobado_at",
                "cerrado_por", "cerrado_at",
                "observaciones",
            )
        }),
    )
    readonly_fields = (
        "total_percepciones",
        "total_deducciones",
        "total_neto",
        "total_aportes_patronales",
        "total_costo_empresa",
        "empleados_procesados",
        "calculado_por", "calculado_at",
        "aprobado_por", "aprobado_at",
        "cerrado_por", "cerrado_at",
    )

    @admin.display(description="Estatus")
    def estatus_badge(self, obj):
        colores = {
            "abierto": "#6b7280",
            "calculado": "#2563eb",
            "aprobado": "#0891b2",
            "pagado": "#059669",
            "cerrado": "#374151",
            "cancelado": "#dc2626",
        }
        color = colores.get(obj.estatus, "#6b7280")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:10px;font-size:11px;">{}</span>',
            color,
            obj.get_estatus_display(),
        )

    @admin.display(description="Neto a pagar")
    def total_neto_fmt(self, obj):
        return f"Bs. {obj.total_neto:,.2f}"

    @admin.action(description="Calcular nómina del periodo seleccionado")
    def accion_calcular(self, request, queryset):
        from .nomina.engine import calcular_periodo, NominaError

        for periodo in queryset:
            if periodo.estatus not in ("abierto", "calculado"):
                self.message_user(
                    request,
                    f"Periodo {periodo.id}: no se puede calcular en estado "
                    f"'{periodo.get_estatus_display()}'.",
                    level=messages.WARNING,
                )
                continue

            try:
                resultado = calcular_periodo(periodo, usuario=request.user)
                self.message_user(
                    request,
                    f"✅ Periodo {periodo.id}: "
                    f"{resultado['empleados_procesados']} empleados procesados. "
                    f"Neto: Bs. {resultado['total_neto']:,.2f}.",
                    level=messages.SUCCESS,
                )
                for err in resultado.get("errores", []):
                    self.message_user(
                        request,
                        f"⚠️ {err['empleado']} - {err['nombre']}: {err['error']}",
                        level=messages.WARNING,
                    )
            except NominaError as e:
                self.message_user(
                    request,
                    f"❌ Periodo {periodo.id}: {e}",
                    level=messages.ERROR,
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ Periodo {periodo.id}: error inesperado - {e}",
                    level=messages.ERROR,
                )

    @admin.action(description="Aprobar nómina (debe estar calculada)")
    def accion_aprobar(self, request, queryset):
        actualizados = 0
        for periodo in queryset:
            if periodo.estatus == "calculado":
                periodo.estatus = "aprobado"
                periodo.aprobado_por = request.user
                periodo.aprobado_at = timezone.now()
                periodo.save()
                actualizados += 1

        self.message_user(
            request,
            f"{actualizados} periodo(s) aprobado(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="Cerrar nómina (no se puede modificar después)")
    def accion_cerrar(self, request, queryset):
        actualizados = 0
        for periodo in queryset:
            if periodo.estatus in ("aprobado", "pagado"):
                periodo.estatus = "cerrado"
                periodo.cerrado_por = request.user
                periodo.cerrado_at = timezone.now()
                periodo.save()
                actualizados += 1

        self.message_user(
            request,
            f"{actualizados} periodo(s) cerrado(s).",
            level=messages.SUCCESS,
        )


# ═══════════════════════════════════════════════════════════
#  NÓMINA POR EMPLEADO
# ═══════════════════════════════════════════════════════════

class NominaDetalleInline(admin.TabularInline):
    model = NominaDetalle
    extra = 0
    fields = (
        "codigo_concepto",
        "nombre_concepto",
        "tipo",
        "cantidad",
        "base_calculo",
        "importe",
        "gravado",
        "exento",
    )
    readonly_fields = (
        "codigo_concepto",
        "nombre_concepto",
        "tipo",
        "cantidad",
        "base_calculo",
        "importe",
        "gravado",
        "exento",
    )
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(NominaEmpleado)
class NominaEmpleadoAdmin(admin.ModelAdmin):
    list_display = (
        "empleado",
        "periodo",
        "dias_trabajados",
        "total_percepciones",
        "total_deducciones",
        "neto_pagar",
        "estatus",
        "acciones_recibo",        # ← Aquí SÍ va
    )
    list_filter = (
        "estatus",
        "periodo__empresa",
        "periodo__tipo",
        "periodo__anio",
    )
    search_fields = (
        "empleado__nombre",
        "empleado__apellido_paterno",
        "empleado__numero_empleado",
        "empleado__cedula",
    )
    autocomplete_fields = ("empleado", "periodo")
    inlines = [NominaDetalleInline]
    list_per_page = 30

    fieldsets = (
        ("Identificación", {
            "fields": ("periodo", "empleado", "estatus")
        }),
        ("Datos base", {
            "fields": (
                "salario_base",
                "salario_diario",
                "salario_normal",
                "salario_integral",
                "dias_periodo",
                "dias_trabajados",
                "dias_faltas",
                "dias_vacaciones",
                "dias_incapacidad",
            )
        }),
        ("Horas", {
            "fields": (
                "horas_extra_diurnas",
                "horas_extra_nocturnas",
                "horas_nocturnas",
            ),
            "classes": ("collapse",),
        }),
        ("Totales", {
            "fields": (
                "total_percepciones",
                "total_deducciones",
                "neto_pagar",
                "total_aportes_patronales",
                "costo_total_empresa",
            )
        }),
        ("Bases", {
            "fields": (
                "base_islr",
                "islr_calculado",
                "base_ivss",
                "ivss_obrero",
            ),
            "classes": ("collapse",),
        }),
        ("Recibo", {
            "fields": ("acciones_recibo",),
        }),
    )
    readonly_fields = (
        "salario_integral",
        "total_percepciones",
        "total_deducciones",
        "neto_pagar",
        "total_aportes_patronales",
        "costo_total_empresa",
        "islr_calculado",
        "ivss_obrero",
        "acciones_recibo",       # ← para el detalle
    )

    # ═══════════════════════════════════════════════════
    #  COLUMNA "RECIBO" EN LA LISTA
    # ═══════════════════════════════════════════════════

    @admin.display(description="Recibo")
    def acciones_recibo(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:rrhh_nominaempleado_recibo", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" target="_blank" '
            'style="background:#059669;color:white;padding:3px 10px;'
            'border-radius:4px;font-size:11px;text-decoration:none;">'
            '📄 Ver PDF</a>',
            url,
        )

    # ═══════════════════════════════════════════════════
    #  URL PERSONALIZADA PARA EL PDF
    # ═══════════════════════════════════════════════════

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/recibo/",
                self.admin_site.admin_view(self.ver_recibo),
                name="rrhh_nominaempleado_recibo",
            ),
        ]
        return custom_urls + urls

    def ver_recibo(self, request, pk):
        """Genera y devuelve el PDF del recibo."""
        from django.http import HttpResponse, HttpResponseServerError
        from django.shortcuts import get_object_or_404
        from .nomina.pdf.recibo import generar_recibo_pdf

        nomina = get_object_or_404(NominaEmpleado, pk=pk)

        try:
            pdf_bytes = generar_recibo_pdf(nomina)
        except RuntimeError as e:
            return HttpResponseServerError(str(e))

        filename = (
            f"recibo_{nomina.empleado.numero_empleado}_"
            f"{nomina.periodo.anio}_{nomina.periodo.numero_periodo}.pdf"
        )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


@admin.register(NominaDetalle)
class NominaDetalleAdmin(admin.ModelAdmin):
    list_display = (
        "nomina",
        "codigo_concepto",
        "nombre_concepto",
        "tipo",
        "importe",
        "gravado",
        "exento",
    )
    list_filter = ("tipo", "naturaleza")
    search_fields = (
        "codigo_concepto",
        "nombre_concepto",
        "nomina__empleado__nombre",
        "nomina__empleado__numero_empleado",
    )
    list_per_page = 50
    ordering = ("-nomina__periodo__fecha_pago", "orden")


# ═══════════════════════════════════════════════════════════
#  INCIDENCIAS DE NÓMINA
# ═══════════════════════════════════════════════════════════

@admin.register(IncidenciaNomina)
class IncidenciaNominaAdmin(admin.ModelAdmin):
    list_display = (
        "empleado",
        "tipo",
        "fecha",
        "cantidad",
        "unidad",
        "estatus_badge",
        "periodo",
    )
    list_filter = (
        "tipo",
        "estatus",
        "periodo__empresa",
        "periodo__anio",
    )
    search_fields = (
        "empleado__nombre",
        "empleado__apellido_paterno",
        "empleado__numero_empleado",
    )
    autocomplete_fields = ("empleado", "periodo")
    date_hierarchy = "fecha"
    list_per_page = 30
    actions = ["accion_aprobar", "accion_rechazar"]

    fieldsets = (
        ("Identificación", {
            "fields": ("empleado", "periodo", "tipo")
        }),
        ("Detalle", {
            "fields": ("fecha", "cantidad", "unidad", "motivo")
        }),
        ("Soporte", {
            "fields": ("documento_soporte",),
            "classes": ("collapse",),
        }),
        ("Estatus", {
            "fields": (
                "estatus",
                "aprobado_por",
                "aprobado_at",
            )
        }),
    )
    readonly_fields = ("aprobado_por", "aprobado_at")

    @admin.display(description="Estatus")
    def estatus_badge(self, obj):
        colores = {
            "pendiente": "#d97706",
            "aprobada": "#059669",
            "rechazada": "#dc2626",
            "aplicada": "#2563eb",
        }
        color = colores.get(obj.estatus, "#6b7280")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:10px;font-size:11px;">{}</span>',
            color,
            obj.get_estatus_display(),
        )

    @admin.action(description="Aprobar incidencias seleccionadas")
    def accion_aprobar(self, request, queryset):
        actualizados = queryset.filter(estatus="pendiente").update(
            estatus="aprobada",
            aprobado_por=request.user,
            aprobado_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{actualizados} incidencia(s) aprobada(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="Rechazar incidencias seleccionadas")
    def accion_rechazar(self, request, queryset):
        actualizados = queryset.filter(estatus="pendiente").update(
            estatus="rechazada",
        )
        self.message_user(
            request,
            f"{actualizados} incidencia(s) rechazada(s).",
            level=messages.SUCCESS,
        )
        

# ═══════════════════════════════════════════════════════════
#  TIPOS DE AUSENCIA
# ═══════════════════════════════════════════════════════════

@admin.register(TipoAusencia)
class TipoAusenciaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "nombre", "categoria",
        "con_goce_sueldo", "afecta_nomina",
        "afecta_saldo_vacaciones", "activo",
    )
    list_filter = (
        "categoria", "con_goce_sueldo", "afecta_nomina",
        "afecta_saldo_vacaciones", "activo", "empresa",
    )
    search_fields = ("codigo", "nombre")
    autocomplete_fields = ("empresa",)
    list_per_page = 25

    fieldsets = (
        ("Identificación", {
            "fields": ("empresa", "codigo", "nombre", "descripcion", "categoria")
        }),
        ("Reglas de negocio", {
            "fields": (
                "con_goce_sueldo",
                "requiere_aprobacion",
                "afecta_nomina",
                "afecta_saldo_vacaciones",
                "requiere_comprobante",
            )
        }),
        ("Límites", {
            "fields": (
                "dias_max_anuales",
                "dias_max_por_solicitud",
                "dias_antelacion_minima",
            )
        }),
        ("Estado", {
            "fields": ("activo",)
        }),
    )


# ═══════════════════════════════════════════════════════════
#  SALDO DE VACACIONES
# ═══════════════════════════════════════════════════════════

class MovimientoSaldoInline(admin.TabularInline):
    model = MovimientoSaldoVacaciones
    extra = 0
    fields = ("tipo", "dias", "saldo_anterior", "saldo_nuevo", "motivo", "created_at")
    readonly_fields = ("saldo_anterior", "saldo_nuevo", "created_at")
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SaldoVacaciones)
class SaldoVacacionesAdmin(admin.ModelAdmin):
    list_display = (
        "empleado", "anio",
        "dias_derecho", "dias_tomados", "dias_pagados",
        "dias_ajuste", "dias_pendientes_display",
    )
    list_filter = ("anio", "empleado__empresa", "empleado__departamento")
    search_fields = (
        "empleado__nombre", "empleado__apellido_paterno",
        "empleado__numero_empleado", "empleado__cedula",
    )
    autocomplete_fields = ("empleado",)
    list_per_page = 30
    readonly_fields = ("created_at", "updated_at")
    inlines = [MovimientoSaldoInline]

    fieldsets = (
        ("Identificación", {
            "fields": ("empleado", "anio", "fecha_limite_uso")
        }),
        ("Días", {
            "fields": (
                "dias_derecho",
                "dias_tomados",
                "dias_pagados",
                "dias_ajuste",
            )
        }),
        ("Observaciones", {
            "fields": ("observaciones",)
        }),
        ("Auditoría", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Días pendientes")
    def dias_pendientes_display(self, obj):
        from django.utils.html import format_html
        pendientes = obj.dias_pendientes
        color = "#059669" if pendientes > 0 else "#dc2626"
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color, pendientes,
        )


# ═══════════════════════════════════════════════════════════
#  SOLICITUDES DE AUSENCIA
# ═══════════════════════════════════════════════════════════

@admin.register(SolicitudAusencia)
class SolicitudAusenciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "empleado",
        "tipo",
        "fecha_inicio",
        "fecha_fin",
        "dias_solicitados",
        "estatus_badge",
        "aprobador",
    )
    list_filter = (
        "estatus", "tipo", "empleado__empresa",
        "empleado__departamento", "fecha_inicio",
    )
    search_fields = (
        "empleado__nombre", "empleado__apellido_paterno",
        "empleado__numero_empleado", "empleado__cedula",
        "motivo",
    )
    autocomplete_fields = ("empleado", "tipo", "aprobador", "incidencia_generada")
    date_hierarchy = "fecha_inicio"
    list_per_page = 30
    readonly_fields = (
        "fecha_solicitud", "fecha_resolucion",
        "incidencia_generada", "created_at", "updated_at",
    )

    fieldsets = (
        ("Identificación", {
            "fields": ("empleado", "tipo", "estatus")
        }),
        ("Fechas", {
            "fields": (
                "fecha_inicio",
                "fecha_fin",
                "dias_solicitados",
                "dias_calendario",
                "fecha_reincorporacion",
            )
        }),
        ("Detalles", {
            "fields": ("motivo", "comprobante")
        }),
        ("Aprobación", {
            "fields": (
                "aprobador",
                "fecha_solicitud",
                "fecha_resolucion",
                "comentario_aprobador",
            )
        }),
        ("Integración con nómina", {
            "fields": ("incidencia_generada",),
            "classes": ("collapse",),
        }),
        ("Auditoría", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["accion_aprobar", "accion_rechazar"]

    @admin.display(description="Estatus")
    def estatus_badge(self, obj):
        from django.utils.html import format_html
        colores = {
            "borrador": "#6b7280",
            "pendiente": "#d97706",
            "aprobada": "#059669",
            "rechazada": "#dc2626",
            "cancelada": "#6b7280",
            "en_disfrute": "#2563eb",
            "finalizada": "#374151",
        }
        color = colores.get(obj.estatus, "#6b7280")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:10px;font-size:11px;">{}</span>',
            color,
            obj.get_estatus_display(),
        )

    @admin.action(description="✅ Aprobar solicitudes seleccionadas")
    def accion_aprobar(self, request, queryset):
        from django.utils import timezone
        actualizadas = 0
        for solicitud in queryset.filter(estatus="pendiente"):
            solicitud.estatus = "aprobada"
            solicitud.aprobador = solicitud.empleado.jefe or solicitud.empleado
            solicitud.fecha_resolucion = timezone.now()
            solicitud.save()
            actualizadas += 1

        self.message_user(
            request,
            f"{actualizadas} solicitud(es) aprobada(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="❌ Rechazar solicitudes seleccionadas")
    def accion_rechazar(self, request, queryset):
        from django.utils import timezone
        actualizadas = 0
        for solicitud in queryset.filter(estatus="pendiente"):
            solicitud.estatus = "rechazada"
            solicitud.fecha_resolucion = timezone.now()
            solicitud.save()
            actualizadas += 1

        self.message_user(
            request,
            f"{actualizadas} solicitud(es) rechazada(s).",
            level=messages.WARNING,
        )


# ═══════════════════════════════════════════════════════════
#  MOVIMIENTOS DE SALDO (solo lectura)
# ═══════════════════════════════════════════════════════════

@admin.register(MovimientoSaldoVacaciones)
class MovimientoSaldoVacacionesAdmin(admin.ModelAdmin):
    list_display = (
        "saldo", "tipo", "dias",
        "saldo_anterior", "saldo_nuevo",
        "usuario", "created_at",
    )
    list_filter = ("tipo", "created_at")
    search_fields = (
        "saldo__empleado__nombre",
        "saldo__empleado__apellido_paterno",
        "saldo__empleado__numero_empleado",
    )
    readonly_fields = (
        "saldo", "tipo", "dias", "saldo_anterior",
        "saldo_nuevo", "solicitud", "motivo", "usuario", "created_at",
    )
    date_hierarchy = "created_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE VACACIONES
# ═══════════════════════════════════════════════════════════

@admin.register(ConfiguracionVacaciones)
class ConfiguracionVacacionesAdmin(admin.ModelAdmin):
    list_display = [
        "empresa", "aplica_contrato_colectivo", "dias_base_vacaciones",
        "dias_base_bono_vacacional", "meses_vencimiento", "activa",
    ]
    list_filter = ["aplica_contrato_colectivo", "activa"]
    search_fields = ["empresa__razon_social", "empresa__rif", "nombre_contrato_colectivo"]
    autocomplete_fields = ["empresa"]
    fieldsets = [
        ("Empresa", {
            "fields": ["empresa", "activa"],
        }),
        ("Reglas LOTTT (defaults)", {
            "fields": [
                "dias_base_vacaciones",
                "dias_base_bono_vacacional",
                "dias_max_vacaciones",
                "dias_max_bono_vacacional",
                "incremento_anual_vacaciones",
                "incremento_anual_bono",
            ],
        }),
        ("Contrato colectivo (opcional)", {
            "fields": [
                "aplica_contrato_colectivo",
                "nombre_contrato_colectivo",
                "cc_dias_vacaciones",
                "cc_dias_bono_vacacional",
                "cc_incremento_anual_vacaciones",
                "cc_incremento_anual_bono",
                "cc_dias_max_vacaciones",
                "cc_dias_max_bono",
            ],
            "classes": ["collapse"],
        }),
        ("Vencimiento", {
            "fields": ["meses_vencimiento"],
        }),
        ("Vacaciones colectivas", {
            "fields": ["permite_vacaciones_colectivas", "dias_colectivos_max"],
        }),
        ("Antelación de solicitudes", {
            "fields": ["dias_antelacion_solicitud"],
        }),
    ]


# ═══════════════════════════════════════════════════════════
#  VACACIONES COLECTIVAS
# ═══════════════════════════════════════════════════════════

@admin.register(VacacionColectiva)
class VacacionColectivaAdmin(admin.ModelAdmin):
    list_display = [
        "nombre", "empresa", "fecha_inicio", "fecha_fin",
        "dias_habiles", "estatus", "total_solicitudes",
    ]
    list_filter = ["estatus", "empresa", "alcance"]
    search_fields = ["nombre", "empresa__razon_social"]
    autocomplete_fields = ["empresa", "sede", "departamento", "tipo_ausencia"]
    readonly_fields = [
        "dias_habiles", "estatus", "aplicada_por", "aplicada_at",
        "created_by", "created_at", "updated_at",
    ]
    fieldsets = [
        ("Datos generales", {
            "fields": ["empresa", "nombre", "observaciones"],
        }),
        ("Alcance", {
            "fields": ["alcance", "sede", "departamento"],
        }),
        ("Fechas", {
            "fields": ["fecha_inicio", "fecha_fin", "dias_habiles"],
        }),
        ("Configuración", {
            "fields": ["tipo_ausencia"],
        }),
        ("Estado", {
            "fields": [
                "estatus", "aplicada_por", "aplicada_at",
            ],
        }),
        ("Auditoría", {
            "fields": ["created_by", "created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        # Recalcular días hábiles
        from rrhh.ausencias.vacaciones_engine import dias_habiles_entre
        if obj.fecha_inicio and obj.fecha_fin:
            obj.dias_habiles = dias_habiles_entre(obj.fecha_inicio, obj.fecha_fin)
        super().save_model(request, obj, form, change)        