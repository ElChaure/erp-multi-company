from django.urls import path

from . import views


app_name = "reportes"

urlpatterns = [
    path(
        "nomina/costo-por-departamento/",
        views.CostoPorDepartamentoView.as_view(),
        name="costo_por_departamento",
    ),
    path(
        "nomina/costo-por-cargo/",
        views.CostoPorCargoView.as_view(),
        name="costo_por_cargo",
    ),
    path(
        "nomina/retenciones-islr/",
        views.RetencionesISLRView.as_view(),
        name="retenciones_islr",
    ),
    path(
        "nomina/aportes-entes/",
        views.AportesEntesView.as_view(),
        name="aportes_entes",
    ),
    path(
        "nomina/resumen-periodos/",
        views.ResumenPorPeriodoView.as_view(),
        name="resumen_periodos",
    ),
    path(
        "nomina/resumen-consolidado/",
        views.ResumenConsolidadoView.as_view(),
        name="resumen_consolidado",
    ),
    path(
        "nomina/evolucion-mensual/",
        views.EvolucionMensualView.as_view(),
        name="evolucion_mensual",
    ),
    
    # ─── Reportes maestros ────────────────────────────
    path("maestros/empresas/", views.ReporteEmpresasView.as_view(), name="reporte_empresas"),
    path("maestros/sedes/", views.ReporteSedesView.as_view(), name="reporte_sedes"),
    path("maestros/departamentos/", views.ReporteDepartamentosView.as_view(), name="reporte_departamentos"),
    path("maestros/cargos/", views.ReporteCargosView.as_view(), name="reporte_cargos"),
    path("maestros/empleados/", views.ReporteEmpleadosView.as_view(), name="reporte_empleados"),
    path("maestros/conceptos/", views.ReporteConceptosView.as_view(), name="reporte_conceptos"),
    path("maestros/parametros/", views.ReporteParametrosView.as_view(), name="reporte_parametros"),
    path("maestros/incidencias/", views.ReporteIncidenciasView.as_view(), name="reporte_incidencias"),
    
]