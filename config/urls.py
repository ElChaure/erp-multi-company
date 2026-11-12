from django.contrib import admin
admin.site.site_url = "/rrhh/"
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from rrhh.reportes import admin_views

admin.site.site_header = "RRHH System — Administración"
admin.site.site_title = "RRHH System Admin"
admin.site.index_title = "Panel de Administración"

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # ═══════════════════════════════════════════════════════
    #  REPORTES EN EL ADMIN
    #  IMPORTANTE: van ANTES del path("admin/", ...)
    # ═══════════════════════════════════════════════════════

    path(
        "admin/reportes/",
        admin_views.reportes_index,
        name="reporte_admin_index",
    ),
    path(
        "admin/reportes/empresas/",
        admin_views.reporte_empresas,
        name="reporte_admin_empresas",
    ),
    path(
        "admin/reportes/sedes/",
        admin_views.reporte_sedes,
        name="reporte_admin_sedes",
    ),
    path(
        "admin/reportes/departamentos/",
        admin_views.reporte_departamentos,
        name="reporte_admin_departamentos",
    ),
    path(
        "admin/reportes/cargos/",
        admin_views.reporte_cargos,
        name="reporte_admin_cargos",
    ),
    path(
        "admin/reportes/empleados/",
        admin_views.reporte_empleados,
        name="reporte_admin_empleados",
    ),
    path(
        "admin/reportes/conceptos/",
        admin_views.reporte_conceptos,
        name="reporte_admin_conceptos",
    ),
    path(
        "admin/reportes/parametros/",
        admin_views.reporte_parametros,
        name="reporte_admin_parametros",
    ),
    path(
        "admin/reportes/incidencias/",
        admin_views.reporte_incidencias,
        name="reporte_admin_incidencias",
    ),
    path(
        "admin/reportes/nomina/costo-departamento/",
        admin_views.reporte_costo_departamento,
        name="reporte_admin_costo_departamento",
    ),
    path(
        "admin/reportes/nomina/costo-cargo/",
        admin_views.reporte_costo_cargo,
        name="reporte_admin_costo_cargo",
    ),
    path(
        "admin/reportes/nomina/retenciones-islr/",
        admin_views.reporte_retenciones_islr,
        name="reporte_admin_retenciones_islr",
    ),
    path(
        "admin/reportes/nomina/aportes-entes/",
        admin_views.reporte_aportes_entes,
        name="reporte_admin_aportes_entes",
    ),
    path(
        "admin/reportes/nomina/resumen-periodos/",
        admin_views.reporte_resumen_periodos,
        name="reporte_admin_resumen_periodos",
    ),

    # Reportes de Ausencias
    path(
        "admin/reportes/ausencias/saldos/",
        admin_views.reporte_saldos_vacaciones,
        name="reporte_admin_ausencias_saldos",
    ),
    path(
        "admin/reportes/ausencias/solicitudes/",
        admin_views.reporte_solicitudes_ausencia,
        name="reporte_admin_ausencias_solicitudes",
    ),
    path(
        "admin/reportes/ausencias/proximas/",
        admin_views.reporte_proximas_ausencias,
        name="reporte_admin_ausencias_proximas",
    ),
    path(
        "admin/reportes/ausencias/departamento/",
        admin_views.reporte_ausencias_departamento,
        name="reporte_admin_ausencias_departamento",
    ),
    path(
        "admin/reportes/ausencias/tipo/",
        admin_views.reporte_ausencias_tipo,
        name="reporte_admin_ausencias_tipo",
    ),

    # Reportes de Auditoría
    path(
        "admin/reportes/auditoria/",
        admin_views.reporte_auditoria,
        name="reporte_admin_auditoria",
    ),
    path(
        "admin/reportes/auditoria/por-usuario/",
        admin_views.reporte_auditoria_por_usuario,
        name="reporte_admin_auditoria_por_usuario",
    ),
    path(
        "admin/reportes/auditoria/por-tabla/",
        admin_views.reporte_auditoria_por_tabla,
        name="reporte_admin_auditoria_por_tabla",
    ),
    path(
        "admin/reportes/auditoria/por-accion/",
        admin_views.reporte_auditoria_por_accion,
        name="reporte_admin_auditoria_por_accion",
    ),
    path(
        "admin/reportes/auditoria/diaria/",
        admin_views.reporte_auditoria_diaria,
        name="reporte_admin_auditoria_diaria",
    ),

    path("api/v1/empleado/", include("rrhh.portal_empleado.api_urls")),

    # ═══════════════════════════════════════════════════════
    #  ADMIN DE DJANGO (catch-all, va al final)
    # ═══════════════════════════════════════════════════════
    path("admin/", admin.site.urls),

    # ═══════════════════════════════════════════════════════
    #  WEB (HTML)
    # ═══════════════════════════════════════════════════════
    path("rrhh/", include("rrhh.urls")),

    # ═══════════════════════════════════════════════════════
    #  API REST
    # ═══════════════════════════════════════════════════════
    path("api/v1/", include("rrhh.api_urls")),

    # ═══════════════════════════════════════════════════════
    #  DOCUMENTACIÓN DE LA API
    # ═══════════════════════════════════════════════════════
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    
    path("contabilidad/", include("contabilidad.urls")),
    
]

# ─── Solo en desarrollo: servir archivos media ───
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)