from django.urls import path
from . import vacaciones_views as views


# Sin app_name (Convención B, consistente con nomina y prestaciones)
urlpatterns = [
    path("", views.vacaciones_lista, name="vacaciones_lista"),
    path(
        "vencimientos/",
        views.vacaciones_vencimientos,
        name="vacaciones_vencimientos",
    ),
    path(
        "colectivas/",
        views.vacaciones_colectivas_lista,
        name="vacaciones_colectivas_lista",
    ),
    path(
        "colectivas/nueva/",
        views.vacaciones_colectiva_nueva,
        name="vacaciones_colectiva_nueva",
    ),
    path(
        "colectivas/<int:vacacion_id>/",
        views.vacaciones_colectiva_detalle,
        name="vacaciones_colectiva_detalle",
    ),
    path(
        "colectivas/<int:vacacion_id>/aplicar/",
        views.aplicar_colectiva_view,
        name="vacaciones_aplicar_colectiva",
    ),
    path(
        "<int:empleado_id>/",
        views.vacaciones_detalle,
        name="vacaciones_detalle",
    ),
    path(
        "<int:empleado_id>/ajustar/",
        views.vacaciones_ajustar,
        name="vacaciones_ajustar",
    ),
    path(
        "<int:empleado_id>/recalcular/",
        views.vacaciones_recalcular,
        name="vacaciones_recalcular",
    ),
]