from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.http import HttpResponse

from .models import (Empleado, Departamento, Cargo, Empresa, Sede, Perfil,
    ParametroNomina, ConceptoNomina, PeriodoNomina,
    NominaEmpleado, NominaDetalle, IncidenciaNomina,
)
    
from .serializers import (
    EmpleadoSerializer,
    EmpleadoListSerializer,
    DepartamentoSerializer,
    CargoSerializer,
    EmpresaSerializer,
    SedeSerializer,
    UsuarioSerializer,
    LoginSerializer,
    ParametroNominaSerializer,
    ConceptoNominaSerializer,
    PeriodoNominaSerializer,
    PeriodoNominaSimpleSerializer,
    NominaEmpleadoSerializer,
    NominaEmpleadoListSerializer,
    IncidenciaNominaSerializer,
    MiReciboListSerializer,
)

from .permissions import (
    EsRRHH,
    EsAdmin,
    SoloLecturaOEsRRHH,
    EsSuperAdmin,
    EsAdminEmpresa,
    FiltrarPorEmpresaMixin,   
)

from rrhh.auditoria import services as auditoria_services


# ═══════════════════════════════════════════════════════════
#  EMPRESA
# ═══════════════════════════════════════════════════════════

class EmpresaViewSet(viewsets.ModelViewSet):
    """
    CRUD de empresas.
    - Lectura: cualquier autenticado (solo ve su empresa, o todas si es superadmin).
    - Escritura: solo superadmins.
    """
    queryset = Empresa.objects.all().order_by("razon_social")
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ["rif", "razon_social", "nombre_comercial"]
    filterset_fields = ["tipo", "activa"]
    ordering = ["razon_social"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return qs

        if hasattr(user, "perfil"):
            if user.perfil.tiene_acceso_global:
                return qs
            if user.perfil.empresa:
                return qs.filter(id=user.perfil.empresa_id)

        return qs.none()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), EsSuperAdmin()]


# ═══════════════════════════════════════════════════════════
#  SEDE
# ═══════════════════════════════════════════════════════════

class SedeViewSet(FiltrarPorEmpresaMixin, viewsets.ModelViewSet):
    """
    CRUD de sedes.
    - Lectura: todos los autenticados (filtrado por empresa).
    - Escritura: RRHH+.
    - Eliminación: admins.
    """
    queryset = Sede.objects.select_related("empresa").all().order_by("nombre")
    serializer_class = SedeSerializer
    permission_classes = [IsAuthenticated, SoloLecturaOEsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["empresa", "tipo", "activa", "es_principal"]
    search_fields = ["codigo", "nombre", "ciudad"]
    ordering = ["empresa__razon_social", "nombre"]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), EsAdminEmpresa()]
        if self.action in ("create", "update", "partial_update"):
            return [IsAuthenticated(), EsRRHH()]
        return [IsAuthenticated()]



class CargoViewSet(viewsets.ModelViewSet):
    """
    CRUD de cargos.
    - Lectura: todos los autenticados
    - Escritura: solo RRHH/admin
    - Eliminación: solo admin
    """
    queryset = Cargo.objects.all().order_by("nombre")
    serializer_class = CargoSerializer
    permission_classes = [IsAuthenticated, SoloLecturaOEsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["activo"]
    search_fields = ["codigo", "nombre"]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), EsAdmin()]
        if self.action in ("create", "update", "partial_update"):
            return [IsAuthenticated(), EsRRHH()]
        return [IsAuthenticated()]


# ═══════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════

@extend_schema(
    summary="Iniciar sesión",
    description="Autentica al usuario y devuelve los tokens JWT.",
    request=inline_serializer(
        name="LoginRequest",
        fields={
            "username": serializers.CharField(help_text="Nombre de usuario"),
            "password": serializers.CharField(
                style={"input_type": "password"},
                help_text="Contraseña",
            ),
        },
    ),
    responses={
        200: inline_serializer(
            name="LoginResponse",
            fields={
                "access_token": serializers.CharField(),
                "refresh_token": serializers.CharField(),
                "token_type": serializers.CharField(),
                "expires_in": serializers.IntegerField(),
                "usuario": serializers.DictField(),
            },
        ),
        401: inline_serializer(
            name="LoginError",
            fields={"detail": serializers.CharField()},
        ),
    },
    tags=["Autenticación"],
)

class LoginViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        if not user:
            # Registrar intento fallido
            auditoria_services.registrar(
                accion="login_failed",
                descripcion=f"Intento de login fallido: {serializer.validated_data['username']}",
                metadata={"username": serializer.validated_data["username"]},
            )
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "Usuario inactivo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        # Registrar login exitoso
        auditoria_services.registrar_login(usuario=user, exitoso=True)

        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "token_type": "Bearer",
            "expires_in": 8 * 3600,
            "usuario": UsuarioSerializer(user).data,
        })


class LogoutViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        auditoria_services.registrar_logout(usuario=request.user)
        return Response(
            {"detail": "Sesión cerrada correctamente."},
            status=status.HTTP_200_OK,
        )
    
    
class MeViewSet(viewsets.ViewSet):
    """Devuelve el usuario autenticado."""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response(UsuarioSerializer(request.user).data)


# ═══════════════════════════════════════════════════════════
#  EMPLEADOS
# ═══════════════════════════════════════════════════════════

class EmpleadoViewSet(viewsets.ModelViewSet):
    """
    CRUD de empleados.
    
    - Listado y detalle: cualquier usuario autenticado.
    - Creación y edición: solo RRHH y admin.
    - Eliminación: solo admin.
    """
    queryset = Empleado.objects.all().order_by("-fecha_ingreso")
    permission_classes = [IsAuthenticated, SoloLecturaOEsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["estatus"]
    search_fields = ["numero_empleado", "nombre", "apellido_paterno", "email"]
    ordering_fields = ["fecha_ingreso", "salario_base", "numero_empleado"]
    ordering = ["-fecha_ingreso"]

    def get_serializer_class(self):
        if self.action == "list":
            return EmpleadoListSerializer
        return EmpleadoSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), EsAdmin()]
        if self.action in ("create", "update", "partial_update"):
            return [IsAuthenticated(), EsRRHH()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"], url_path="estadisticas")
    def estadisticas(self, request):
        """Devuelve estadísticas agregadas."""
        total = Empleado.objects.count()
        activos = Empleado.objects.filter(estatus="activo").count()
        bajas = Empleado.objects.filter(estatus="baja").count()

        return Response({
            "total": total,
            "activos": activos,
            "bajas": bajas,
            "licencias": Empleado.objects.filter(estatus="licencia").count(),
        })

    @action(detail=True, methods=["post"], url_path="baja")
    def dar_baja(self, request, pk=None):
        """Marca al empleado como baja."""
        empleado = self.get_object()
        empleado.estatus = "baja"
        empleado.save()
        return Response(EmpleadoSerializer(empleado).data)


# ═══════════════════════════════════════════════════════════
#  DEPARTAMENTOS
# ═══════════════════════════════════════════════════════════

class DepartamentoViewSet(viewsets.ModelViewSet):
    """
    CRUD de departamentos.
    
    - Lectura: todos los autenticados.
    - Escritura: solo RRHH y admin.
    - Eliminación: solo admin.
    """
    queryset = Departamento.objects.all().order_by("nombre")
    serializer_class = DepartamentoSerializer
    permission_classes = [IsAuthenticated, SoloLecturaOEsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["activo"]
    search_fields = ["codigo", "nombre"]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), EsAdmin()]
        if self.action in ("create", "update", "partial_update"):
            return [IsAuthenticated(), EsRRHH()]
        return [IsAuthenticated()]


# ═══════════════════════════════════════════════════════════
#  USUARIOS (solo RRHH/admin)
# ═══════════════════════════════════════════════════════════

class UsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    """Listado de usuarios del sistema. Solo RRHH/admin."""
    queryset = User.objects.all().order_by("username")
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, EsRRHH]
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    
# ═══════════════════════════════════════════════════════════
#  PARÁMETROS DE NÓMINA
# ═══════════════════════════════════════════════════════════

class ParametroNominaViewSet(FiltrarPorEmpresaMixin, viewsets.ModelViewSet):
    """
    CRUD de parámetros de nómina (por empresa y año).
    Solo RRHH/admin pueden modificarlos.
    """
    queryset = ParametroNomina.objects.select_related("empresa").all()
    serializer_class = ParametroNominaSerializer
    permission_classes = [IsAuthenticated, EsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["empresa", "anio", "activo"]
    search_fields = ["empresa__razon_social", "anio"]
    ordering_fields = ["anio", "empresa__razon_social"]
    ordering = ["-anio"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return qs

        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(empresa=user.perfil.empresa)

        return qs.none()


# ═══════════════════════════════════════════════════════════
#  CONCEPTOS DE NÓMINA
# ═══════════════════════════════════════════════════════════

class ConceptoNominaViewSet(viewsets.ModelViewSet):
    """
    CRUD de conceptos de nómina.
    Incluye conceptos globales (empresa=null) + los de la empresa del usuario.
    """
    queryset = ConceptoNomina.objects.all().order_by("prioridad", "codigo")
    serializer_class = ConceptoNominaSerializer
    permission_classes = [IsAuthenticated, SoloLecturaOEsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "tipo", "naturaleza", "es_fijo",
        "afecta_isr", "afecta_ivss", "activo",
    ]
    search_fields = ["codigo", "nombre"]
    ordering_fields = ["prioridad", "codigo", "nombre"]
    ordering = ["prioridad", "codigo"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return qs

        if hasattr(user, "perfil") and user.perfil.empresa:
            # Globales + de la empresa
            return qs.filter(
                models.Q(empresa__isnull=True) | models.Q(empresa=user.perfil.empresa)
            )

        return qs.filter(empresa__isnull=True)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), EsRRHH()]
        return [IsAuthenticated()]


# ═══════════════════════════════════════════════════════════
#  PERIODOS DE NÓMINA
# ═══════════════════════════════════════════════════════════

class PeriodoNominaViewSet(FiltrarPorEmpresaMixin, viewsets.ModelViewSet):
    """
    CRUD de periodos de nómina.
    Incluye acciones especiales: calcular, cerrar, nominas.
    """
    queryset = (
        PeriodoNomina.objects
        .select_related("empresa")
        .all()
        .order_by("-fecha_pago")
    )
    permission_classes = [IsAuthenticated, EsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["empresa", "tipo", "anio", "estatus"]
    search_fields = ["numero_periodo", "empresa__razon_social"]
    ordering_fields = ["fecha_pago", "fecha_inicio", "anio", "numero_periodo"]
    ordering = ["-fecha_pago"]

    def get_serializer_class(self):
        if self.action == "list":
            return PeriodoNominaSimpleSerializer
        return PeriodoNominaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return qs

        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(empresa=user.perfil.empresa)

        return qs.none()

    @action(detail=True, methods=["get"], url_path="nominas")
    def nominas(self, request, pk=None):
        """Lista las nóminas de los empleados en este periodo."""
        periodo = self.get_object()
        qs = (
            periodo.nominas
            .select_related("empleado")
            .all()
            .order_by("empleado__apellido_paterno", "empleado__nombre")
        )
        return Response(NominaEmpleadoListSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="calcular")
    def calcular(self, request, pk=None):
        """Calcula la nómina del periodo."""
        from .nomina.engine import calcular_periodo, NominaError

        periodo = self.get_object()

        try:
            resultado = calcular_periodo(periodo, usuario=request.user)
            return Response(resultado)
        except NominaError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {"detail": f"Error inesperado: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], url_path="cerrar")
    def cerrar(self, request, pk=None):
        """Cierra el periodo de nómina (no se puede modificar después)."""
        periodo = self.get_object()

        if not periodo.puede_cerrarse:
            return Response(
                {
                    "detail": (
                        f"No se puede cerrar un periodo en estado "
                        f"'{periodo.get_estatus_display()}'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        periodo.estatus = "cerrado"
        periodo.cerrado_por = request.user
        periodo.cerrado_at = timezone.now()
        periodo.save()

        return Response(PeriodoNominaSerializer(periodo).data)

    @action(detail=True, methods=["post"], url_path="aprobar")
    def aprobar(self, request, pk=None):
        """Aprueba el periodo de nómina (después de calcular)."""
        periodo = self.get_object()

        if periodo.estatus not in ("calculado",):
            return Response(
                {
                    "detail": (
                        f"Solo se pueden aprobar periodos calculados. "
                        f"Estado actual: '{periodo.get_estatus_display()}'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        periodo.estatus = "aprobado"
        periodo.aprobado_por = request.user
        periodo.aprobado_at = timezone.now()
        periodo.save()

        return Response(PeriodoNominaSerializer(periodo).data)


# ═══════════════════════════════════════════════════════════
#  NÓMINA POR EMPLEADO
# ═══════════════════════════════════════════════════════════

class NominaEmpleadoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consulta de nóminas por empleado.

    - RRHH/admin: ven todas las nóminas de su empresa.
    - Empleado normal: solo ve sus propios recibos.
    """
    queryset = (
        NominaEmpleado.objects
        .select_related("empleado", "periodo")
        .prefetch_related("detalles__concepto")
        .all()
        .order_by("-periodo__fecha_pago")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["periodo", "empleado", "estatus"]
    search_fields = [
        "empleado__nombre",
        "empleado__apellido_paterno",
        "empleado__numero_empleado",
        "empleado__cedula",
    ]
    ordering_fields = ["neto_pagar", "total_percepciones", "periodo__fecha_pago"]
    ordering = ["-periodo__fecha_pago"]

    def get_serializer_class(self):
        if self.action == "list":
            return NominaEmpleadoListSerializer
        return NominaEmpleadoSerializer

    def _perfil(self):
        return getattr(self.request.user, "perfil", None)

    def _es_rrhh_o_superior(self):
        perfil = self._perfil()
        if not perfil:
            return self.request.user.is_superuser
        return perfil.rol in ("superadmin", "admin", "rrhh") or self.request.user.is_superuser

    def _empleado_del_usuario(self):
        """Devuelve el Empleado asociado al usuario logueado, o None."""
        perfil = self._perfil()
        if not perfil:
            return None
        return getattr(perfil, "empleado", None)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return qs

        perfil = self._perfil()
        if not perfil:
            return qs.none()

        # RRHH / admin: ven toda su empresa
        if perfil.rol in ("superadmin", "admin", "rrhh"):
            if perfil.empresa_id:
                return qs.filter(empleado__empresa_id=perfil.empresa_id)
            return qs

        # Manager / empleado: solo sus propios recibos
        empleado = self._empleado_del_usuario()
        if empleado:
            return qs.filter(empleado=empleado)

        return qs.none()

    @action(detail=False, methods=["get"], url_path="mis-recibos")
    def mis_recibos(self, request):
        """
        Listado paginado de recibos del empleado logueado.
        Solo muestra periodos en estado 'pagado' o 'cerrado'.

        Query params:
        - anio (int, opcional): filtrar por año del periodo.
        - page (int, opcional): número de página.
        """
        from .serializers import MiReciboListSerializer

        empleado = self._empleado_del_usuario()

        if not empleado:
            return Response(
                {
                    "detail": "Tu usuario no está vinculado a un empleado. "
                              "Contacta a RRHH.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = (
            NominaEmpleado.objects
            .filter(
                empleado=empleado,
                periodo__estatus__in=["pagado", "cerrado"],
            )
            .select_related("periodo")
            .order_by("-periodo__fecha_pago")
        )

        # Filtro por año
        anio = request.query_params.get("anio")
        if anio:
            try:
                qs = qs.filter(periodo__anio=int(anio))
            except (ValueError, TypeError):
                pass

        # Paginación
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = MiReciboListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MiReciboListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="mis-anios")
    def mis_anios(self, request):
        """
        Años disponibles de recibos del empleado logueado.
        Útil para poblar el filtro de año en el portal.
        """
        empleado = self._empleado_del_usuario()

        if not empleado:
            return Response({"anios": []})

        anios = (
            NominaEmpleado.objects
            .filter(
                empleado=empleado,
                periodo__estatus__in=["pagado", "cerrado"],
            )
            .values_list("periodo__anio", flat=True)
            .distinct()
            .order_by("-periodo__anio")
        )

        return Response({"anios": list(anios)})

    @action(detail=True, methods=["get"], url_path="recibo")
    def recibo(self, request, pk=None):
        """
        Genera y devuelve el PDF del recibo.
        Aplica las mismas reglas de visibilidad que el listado.
        """
        from django.http import HttpResponse
        from .nomina.pdf.recibo import generar_recibo_pdf

        # Aseguramos que el queryset ya filtre por permisos
        nomina = self.get_object()

        # Validación adicional: empleado normal solo puede ver sus propios recibos
        if not self._es_rrhh_o_superior():
            empleado = self._empleado_del_usuario()
            if not empleado or nomina.empleado_id != empleado.id:
                return Response(
                    {"detail": "No tienes permiso para ver este recibo."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Validación: solo estados pagado/cerrado para el propio empleado
        if nomina.periodo.estatus not in ("pagado", "cerrado"):
            if not self._es_rrhh_o_superior():
                return Response(
                    {"detail": "Este recibo aún no está disponible."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            pdf_bytes = generar_recibo_pdf(nomina)
        except RuntimeError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        filename = (
            f"recibo_{nomina.empleado.numero_empleado}_"
            f"{nomina.periodo.anio}_{nomina.periodo.numero_periodo}.pdf"
        )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

# ═══════════════════════════════════════════════════════════
#  INCIDENCIAS DE NÓMINA
# ═══════════════════════════════════════════════════════════

class IncidenciaNominaViewSet(viewsets.ModelViewSet):
    """
    CRUD de incidencias (faltas, horas extra, retardos, etc.).
    Las incidencias aprobadas se aplican al calcular la nómina.
    """
    queryset = (
        IncidenciaNomina.objects
        .select_related("empleado", "periodo")
        .all()
        .order_by("-fecha")
    )
    serializer_class = IncidenciaNominaSerializer
    permission_classes = [IsAuthenticated, EsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["empleado", "periodo", "tipo", "estatus"]
    search_fields = [
        "empleado__nombre",
        "empleado__apellido_paterno",
        "empleado__numero_empleado",
    ]
    ordering_fields = ["fecha", "tipo"]
    ordering = ["-fecha"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return qs

        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(empleado__empresa=user.perfil.empresa)

        return qs.none()

    @action(detail=True, methods=["post"], url_path="aprobar")
    def aprobar(self, request, pk=None):
        """Aprueba la incidencia para que se aplique al cálculo."""
        incidencia = self.get_object()

        if incidencia.estatus == "aprobada":
            return Response(
                {"detail": "La incidencia ya está aprobada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        incidencia.estatus = "aprobada"
        incidencia.aprobado_por = request.user
        incidencia.aprobado_at = timezone.now()
        incidencia.save()

        return Response(IncidenciaNominaSerializer(incidencia).data)

    @action(detail=True, methods=["post"], url_path="rechazar")
    def rechazar(self, request, pk=None):
        """Rechaza la incidencia (no se aplicará al cálculo)."""
        incidencia = self.get_object()

        if incidencia.estatus == "rechazada":
            return Response(
                {"detail": "La incidencia ya está rechazada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        incidencia.estatus = "rechazada"
        incidencia.save()

        return Response(IncidenciaNominaSerializer(incidencia).data)

    @action(detail=False, methods=["get"], url_path="pendientes")
    def pendientes(self, request):
        """Lista las incidencias pendientes de aprobación."""
        qs = self.get_queryset().filter(estatus="pendiente")
        return Response(IncidenciaNominaSerializer(qs, many=True).data)
        