from django.urls import path

from . import api_views


app_name = "dashboard"


urlpatterns = [
    path("resumen/", api_views.DashboardResumenView.as_view(), name="resumen"),
    path("exportar/", api_views.DashboardExportPDFView.as_view(), name="exportar"),
    path("headcount/", api_views.DashboardHeadcountView.as_view(), name="headcount"),
    path("nomina/", api_views.DashboardNominaView.as_view(), name="nomina"),
    path("ausencias/", api_views.DashboardAusenciasView.as_view(), name="ausencias"),
    path("alertas/", api_views.DashboardAlertasView.as_view(), name="alertas"),
    path("actividad/", api_views.DashboardActividadView.as_view(), name="actividad"),
    path("eventos/", api_views.DashboardEventosView.as_view(), name="eventos"),
]