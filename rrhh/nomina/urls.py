from django.urls import path

from . import views


#app_name = "nomina"


urlpatterns = [
    path("", views.periodo_lista, name="nomina_periodo_lista"),
    path("<int:pk>/", views.periodo_detalle, name="nomina_periodo_detalle"),
    path("<int:pk>/calcular/", views.periodo_calcular, name="nomina_periodo_calcular"),
    path("<int:pk>/aprobar/", views.periodo_aprobar, name="nomina_periodo_aprobar"),
    path("<int:pk>/cerrar/", views.periodo_cerrar, name="nomina_periodo_cerrar"),
    path(
        "<int:pk>/generar-txt/<str:codigo_banco>/",
        views.periodo_generar_txt,
        name="nomina_periodo_generar_txt",
    ),
    path(
        "<int:pk>/bancos-api/",
        views.periodo_bancos_api,
        name="nomina_periodo_bancos_api",
    ),
]