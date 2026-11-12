from django.urls import path

from . import admin_views


app_name = "reportes_admin"

urlpatterns = [
    # Índice
    path("", admin_views.reportes_index, name="index"),

    # Maestros
    path("empresas/", admin_views.reporte_empresas, name="empresas"),
    path("sedes/", admin_views.reporte_sedes, name="sedes"),
    path("departamentos/", admin_views.reporte_departamentos, name="departamentos"),
    path("cargos/", admin_views.reporte_cargos, name="cargos"),
    path("empleados/", admin_views.reporte_empleados, name="empleados"),
    path("conceptos/", admin_views.reporte_conceptos, name="conceptos"),
    path("parametros/", admin_views.reporte_parametros, name="parametros"),
    path("incidencias/", admin_views.reporte_incidencias, name="incidencias"),

    # Nómina
    path("nomina/costo-departamento/", admin_views.reporte_costo_departamento, name="costo_departamento"),
    path("nomina/costo-cargo/", admin_views.reporte_costo_cargo, name="costo_cargo"),
    path("nomina/retenciones-islr/", admin_views.reporte_retenciones_islr, name="retenciones_islr"),
    path("nomina/aportes-entes/", admin_views.reporte_aportes_entes, name="aportes_entes"),
    path("nomina/resumen-periodos/", admin_views.reporte_resumen_periodos, name="resumen_periodos"),
]