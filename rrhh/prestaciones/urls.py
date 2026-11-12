from django.urls import path
from . import views

# Sin app_name (Convención B, consistente con rrhh.nomina)
urlpatterns = [
    path("", views.prestacion_lista, name="prestacion_lista"),
    path("<int:empleado_id>/", views.prestacion_detalle, name="prestacion_detalle"),
    path("<int:empleado_id>/calculadora/", views.prestacion_calculadora, name="prestacion_calculadora"),
    path("<int:empleado_id>/recalcular/", views.prestacion_recalcular, name="prestacion_recalcular"),
    path("<int:empleado_id>/liquidar/", views.prestacion_liquidar, name="prestacion_liquidar"),
]