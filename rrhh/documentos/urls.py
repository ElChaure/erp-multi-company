"""
URLs del módulo de documentos.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Listado
    path(
        "",
        views.documento_lista,
        name="documento_lista",
    ),
    # Constancia
    path(
        "empleados/<int:empleado_id>/constancia/",
        views.constancia_form,
        name="constancia_form",
    ),
    # ARC
    path(
        "empleados/<int:empleado_id>/arc/",
        views.arc_form,
        name="arc_form",
    ),
    # Descarga
    path(
        "<int:documento_id>/descargar/",
        views.documento_descargar,
        name="documento_descargar",
    ),
]