"""
URLs del Portal del Empleado.

Todas bajo /api/v1/empleado/
"""
from django.urls import path

from . import auth_views, api_views


app_name = "portal_empleado"


urlpatterns = [
    # ─── Autenticación ───────────────────────────────────
    path(
        "auth/registro/",
        auth_views.RegistroView.as_view(),
        name="registro",
    ),
    path(
        "auth/login/",                          # ← Flexible (recomendado)
        auth_views.LoginView.as_view(),
        name="login",
    ),
    path(
        "auth/login-username/",                 # ← Por username (compatibilidad)
        auth_views.LoginUsernameView.as_view(),
        name="login_username",
    ),
    path(
        "auth/verificar-empleado/",             # ← NUEVO
        auth_views.VerificarEmpleadoView.as_view(),
        name="verificar_empleado",
    ),
    path(
        "auth/refresh/",
        auth_views.RefreshView.as_view(),
        name="refresh",
    ),
    path(
        "auth/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "auth/cambiar-password/",
        auth_views.CambioPasswordView.as_view(),
        name="cambiar_password",
    ),

    # ─── Datos del empleado ──────────────────────────────
    path(
        "mi-cuenta/",
        api_views.MiCuentaView.as_view(),
        name="mi_cuenta",
    ),
    path(
        "perfil/",
        api_views.MiPerfilView.as_view(),
        name="mi_perfil",
    ),

    # ─── Recibos ─────────────────────────────────────────
    path(
        "recibos/",
        api_views.MisRecibosView.as_view(),
        name="mis_recibos",
    ),
    path(
        "recibos/<int:recibo_id>/",
        api_views.MiReciboDetalleView.as_view(),
        name="mi_recibo_detalle",
    ),
    path(
        "recibos/<int:recibo_id>/pdf/",
        api_views.MiReciboPDFView.as_view(),
        name="mi_recibo_pdf",
    ),

    # ─── Vacaciones ──────────────────────────────────────
    path(
        "vacaciones/saldos/",
        api_views.MisVacacionesSaldosView.as_view(),
        name="mis_vacaciones_saldos",
    ),
    path(
        "vacaciones/movimientos/",
        api_views.MisVacacionesMovimientosView.as_view(),
        name="mis_vacaciones_movimientos",
    ),
    path(
        "vacaciones/solicitudes/",
        api_views.MisSolicitudesView.as_view(),
        name="mis_solicitudes",
    ),
    path(
        "vacaciones/solicitudes/<int:solicitud_id>/",
        api_views.MiSolicitudDetalleView.as_view(),
        name="mi_solicitud_detalle",
    ),
    path(
        "vacaciones/solicitudes/<int:solicitud_id>/cancelar/",
        api_views.MiSolicitudCancelarView.as_view(),
        name="mi_solicitud_cancelar",
    ),
]