from django.urls import path, include
from . import views

app_name = "rrhh"

urlpatterns = [
    # ─── Autenticación ───────────────────────────────────
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("perfil/", views.perfil_view, name="perfil"),
    path("acceso-denegado/", views.acceso_denegado, name="acceso_denegado"),

    # ─── Dashboard ───────────────────────────────────────
    path("", views.dashboard, name="dashboard"),
    
    # ─── Portal del empleado ─────────────────────────────
    path("mi-portal/", views.mi_portal, name="mi_portal"),
    
    # ─── Nómina ──────────────────────────────────────────
    path("nomina/", include("rrhh.nomina.urls")),

    # ─── Prestaciones Sociales ───────────────────────────
    path("prestaciones/", include("rrhh.prestaciones.urls")),
    
    # ─── Vacaciones ──────────────────────────────────────
    path("vacaciones/", include("rrhh.ausencias.vacaciones_urls")), 
    
    # ─── Solicitudes de vacaciones ───────────────────────
    path("solicitudes/", include("rrhh.ausencias.solicitud_urls")),
    
    # ─── Empresa ─────────────────────────────────────────
    path("empresas/", views.empresa_lista, name="empresa_lista"),
    path("empresas/nuevo/", views.empresa_crear, name="empresa_crear"),
    path("empresas/<int:pk>/", views.empresa_detalle, name="empresa_detalle"),
    path("empresas/<int:pk>/editar/", views.empresa_editar, name="empresa_editar"),
    path("empresas/<int:pk>/eliminar/", views.empresa_eliminar, name="empresa_eliminar"),

    # ─── Sede ────────────────────────────────────────────
    path("sedes/", views.sede_lista, name="sede_lista"),
    path("sedes/nuevo/", views.sede_crear, name="sede_crear"),
    path("sedes/<int:pk>/", views.sede_detalle, name="sede_detalle"),
    path("sedes/<int:pk>/editar/", views.sede_editar, name="sede_editar"),
    path("sedes/<int:pk>/eliminar/", views.sede_eliminar, name="sede_eliminar"),

    # ─── Empleados ───────────────────────────────────────
    path("empleados/", views.empleado_lista, name="empleado_lista"),
    path("empleados/nuevo/", views.empleado_crear, name="empleado_crear"),
    path("empleados/<int:pk>/", views.empleado_detalle, name="empleado_detalle"),
    path("empleados/<int:pk>/editar/", views.empleado_editar, name="empleado_editar"),
    path("empleados/<int:pk>/eliminar/", views.empleado_eliminar, name="empleado_eliminar"),

    # ─── Cargo ───────────────────────────────────────────
    path("cargos/", views.cargo_lista, name="cargo_lista"),
    path("cargos/nuevo/", views.cargo_crear, name="cargo_crear"),
    path("cargos/<int:pk>/", views.cargo_detalle, name="cargo_detalle"), 
    path("cargos/<int:pk>/editar/", views.cargo_editar, name="cargo_editar"),
    path("cargos/<int:pk>/eliminar/", views.cargo_eliminar, name="cargo_eliminar"),
    
    # ─── Departamento ────────────────────────────────────
    path("departamentos/", views.departamento_lista, name="departamento_lista"),
    path("departamentos/nuevo/", views.departamento_crear, name="departamento_crear"),
    path("departamentos/<int:pk>/", views.departamento_detalle, name="departamento_detalle"),
    path("departamentos/<int:pk>/editar/", views.departamento_editar, name="departamento_editar"),
    path("departamentos/<int:pk>/eliminar/", views.departamento_eliminar, name="departamento_eliminar"),

    # ─── Documentos ──────────────────────────────────────
    path("documentos/", include("rrhh.documentos.urls")),

    # ─── API JSON ────────────────────────────────────────
    path("api/empleados/", views.api_empleados, name="api_empleados"),
    path("api/empresas/<int:empresa_id>/sedes/", views.api_sedes_por_empresa, name="api_sedes_por_empresa"),
    path("api/empresas/<int:empresa_id>/departamentos/", views.api_departamentos_por_empresa, name="api_departamentos_por_empresa"),
]