from django.urls import path
from . import solicitud_views as views


# Sin app_name (Convención B)
urlpatterns = [
    # Empleado
    path("mis/", views.solicitud_mis, name="solicitud_mis"),
    path("nueva/", views.solicitud_nueva, name="solicitud_nueva"),

    # Aprobador (RRHH / manager)
    path("", views.solicitud_lista, name="solicitud_lista"),
    path("<int:solicitud_id>/", views.solicitud_detalle, name="solicitud_detalle"),

    # Acciones POST
    path("<int:solicitud_id>/aprobar/", views.solicitud_aprobar, name="solicitud_aprobar"),
    path("<int:solicitud_id>/rechazar/", views.solicitud_rechazar, name="solicitud_rechazar"),
    path("<int:solicitud_id>/cancelar/", views.solicitud_cancelar, name="solicitud_cancelar"),
]