from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .api_views import (
    EmpleadoViewSet,
    DepartamentoViewSet,
    CargoViewSet,
    EmpresaViewSet,
    SedeViewSet,
    UsuarioViewSet,
    LoginViewSet,
    LogoutViewSet,
    MeViewSet,
    # Nómina
    ParametroNominaViewSet,
    ConceptoNominaViewSet,
    PeriodoNominaViewSet,
    NominaEmpleadoViewSet,
    IncidenciaNominaViewSet,
)

from .ausencias.views import (
    TipoAusenciaViewSet,
    SaldoVacacionesViewSet,
    SolicitudAusenciaViewSet,
    MovimientoSaldoViewSet,
)

router = DefaultRouter()
router.register("empresas", EmpresaViewSet, basename="empresa")
router.register("sedes", SedeViewSet, basename="sede")
router.register("empleados", EmpleadoViewSet, basename="empleado")
router.register("departamentos", DepartamentoViewSet, basename="departamento")
router.register("cargos", CargoViewSet, basename="cargo")
router.register("usuarios", UsuarioViewSet, basename="usuario")
router.register("auth/login", LoginViewSet, basename="login")
router.register("auth/logout", LogoutViewSet, basename="logout")
router.register("auth/me", MeViewSet, basename="me")

# Nómina
router.register("nomina/parametros", ParametroNominaViewSet, basename="parametro-nomina")
router.register("nomina/conceptos", ConceptoNominaViewSet, basename="concepto-nomina")
router.register("nomina/periodos", PeriodoNominaViewSet, basename="periodo-nomina")
router.register("nomina/nominas", NominaEmpleadoViewSet, basename="nomina-empleado")
router.register("nomina/incidencias", IncidenciaNominaViewSet, basename="incidencia-nomina")

# Ausencias
router.register("ausencias/tipos", TipoAusenciaViewSet, basename="tipo-ausencia")
router.register("ausencias/saldos", SaldoVacacionesViewSet, basename="saldo-vacaciones")
router.register("ausencias/solicitudes", SolicitudAusenciaViewSet, basename="solicitud-ausencia")
router.register("ausencias/movimientos", MovimientoSaldoViewSet, basename="movimiento-saldo")


urlpatterns = router.urls + [
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("reportes/", include("rrhh.reportes.urls")),
    path("dashboard/", include("rrhh.dashboard.api_urls")),
]