"""
ViewSets para el módulo de ausencias.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from datetime import timedelta

from ..models import (
    TipoAusencia, SaldoVacaciones, SolicitudAusencia,
    MovimientoSaldoVacaciones,
)
from ..permissions import EsRRHH, SoloLecturaOEsRRHH, FiltrarPorEmpresaMixin
from .serializers import (
    TipoAusenciaSerializer,
    TipoAusenciaSimpleSerializer,
    SaldoVacacionesSerializer,
    SaldoVacacionesSimpleSerializer,
    MovimientoSaldoSerializer,
    SolicitudAusenciaSerializer,
    SolicitudAusenciaListSerializer,
    CrearSolicitudAusenciaSerializer,
)
from . import services


# ═══════════════════════════════════════════════════════════
#  TIPOS DE AUSENCIA
# ═══════════════════════════════════════════════════════════

class TipoAusenciaViewSet(viewsets.ModelViewSet):
    queryset = TipoAusencia.objects.all().order_by("categoria", "nombre")
    serializer_class = TipoAusenciaSerializer
    permission_classes = [IsAuthenticated, SoloLecturaOEsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["categoria", "con_goce_sueldo", "afecta_nomina", "activo"]
    search_fields = ["codigo", "nombre"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(
                models.Q(empresa__isnull=True) | models.Q(empresa=user.perfil.empresa)
            )
        return qs.filter(empresa__isnull=True)


# ═══════════════════════════════════════════════════════════
#  SALDOS DE VACACIONES
# ═══════════════════════════════════════════════════════════

class SaldoVacacionesViewSet(viewsets.ModelViewSet):
    queryset = SaldoVacaciones.objects.select_related("empleado").all()
    permission_classes = [IsAuthenticated, EsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["empleado", "anio", "empleado__empresa"]
    search_fields = [
        "empleado__nombre", "empleado__apellido_paterno",
        "empleado__numero_empleado", "empleado__cedula",
    ]
    ordering = ["-anio", "empleado__apellido_paterno"]

    def get_serializer_class(self):
        if self.action == "list":
            return SaldoVacacionesSimpleSerializer
        return SaldoVacacionesSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(empleado__empresa=user.perfil.empresa)
        return qs.none()

    @action(detail=False, methods=["post"], url_path="recalcular")
    def recalcular(self, request):
        """Recalcula los saldos del año actual para todos los empleados."""
        user = request.user
        empresa = None
        if hasattr(user, "perfil") and user.perfil.empresa:
            empresa = user.perfil.empresa
        elif user.is_superuser:
            empresa_id = request.data.get("empresa_id")
            if empresa_id:
                from ..models import Empresa
                empresa = Empresa.objects.filter(id=empresa_id).first()

        if not empresa:
            return Response(
                {"detail": "No se pudo determinar la empresa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from ..models import Empleado
        from datetime import date

        anio = int(request.data.get("anio", date.today().year))
        empleados = Empleado.objects.filter(empresa=empresa, estatus="activo")
        creados = 0

        for empleado in empleados:
            try:
                saldo = services.obtener_saldo(empleado, anio)
                if saldo:
                    creados += 1
            except Exception:
                pass

        return Response({
            "detail": f"Saldos procesados: {creados}",
            "anio": anio,
            "empresa": empresa.razon_social,
        })
    # ═══════════════════════════════════════════════════════════
    #  PORTAL DEL EMPLEADO
    # ═══════════════════════════════════════════════════════════

    def _empleado_del_usuario(self):
        """Devuelve el Empleado asociado al usuario logueado, o None."""
        perfil = getattr(self.request.user, "perfil", None)
        if not perfil:
            return None
        return getattr(perfil, "empleado", None)

    @action(detail=False, methods=["get"], url_path="mis-saldos")
    def mis_saldos(self, request):
        """
        Devuelve los saldos de vacaciones del empleado logueado.
        Query params:
          - anio (int, opcional): año específico
        """
        empleado = self._empleado_del_usuario()
        if not empleado:
            return Response(
                {"detail": "Tu usuario no está vinculado a un empleado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = SaldoVacaciones.objects.filter(empleado=empleado).order_by("-anio")

        anio = request.query_params.get("anio")
        if anio:
            try:
                qs = qs.filter(anio=int(anio))
            except (ValueError, TypeError):
                pass

        serializer = SaldoVacacionesSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="mis-anios")
    def mis_anios(self, request):
        """Años con saldos registrados para el empleado logueado."""
        empleado = self._empleado_del_usuario()
        if not empleado:
            return Response({"anios": []})

        anios = (
            SaldoVacaciones.objects
            .filter(empleado=empleado)
            .values_list("anio", flat=True)
            .distinct()
            .order_by("-anio")
        )
        return Response({"anios": list(anios)})

# ═══════════════════════════════════════════════════════════
#  SOLICITUDES DE AUSENCIA
# ═══════════════════════════════════════════════════════════

class SolicitudAusenciaViewSet(viewsets.ModelViewSet):
    queryset = SolicitudAusencia.objects.select_related(
        "empleado", "tipo", "aprobador"
    ).all()
    permission_classes = [IsAuthenticated, SoloLecturaOEsRRHH]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "empleado", "tipo", "estatus", "empleado__empresa",
        "empleado__departamento",
    ]
    search_fields = [
        "empleado__nombre", "empleado__apellido_paterno",
        "empleado__numero_empleado", "motivo",
    ]
    ordering = ["-fecha_inicio"]

    def get_serializer_class(self):
        if self.action == "list":
            return SolicitudAusenciaListSerializer
        if self.action == "create":
            return CrearSolicitudAusenciaSerializer
        return SolicitudAusenciaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(empleado__empresa=user.perfil.empresa)
        return qs.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        solicitud = SolicitudAusencia.objects.create(
            empleado=serializer.validated_data["empleado"],
            tipo=serializer.validated_data["tipo"],
            fecha_inicio=serializer.validated_data["fecha_inicio"],
            fecha_fin=serializer.validated_data["fecha_fin"],
            dias_solicitados=serializer.validated_data["dias_solicitados"],
            motivo=serializer.validated_data["motivo"],
            estatus="pendiente",
        )

        # Asignar aprobador (jefe directo)
        if solicitud.empleado.jefe:
            solicitud.aprobador = solicitud.empleado.jefe
            solicitud.save()

        return Response(
            SolicitudAusenciaSerializer(solicitud).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="aprobar")
    def aprobar(self, request, pk=None):
        """Aprueba la solicitud."""
        solicitud = self.get_object()
        comentario = request.data.get("comentario", "")

        aprobador = None
        if hasattr(request.user, "perfil") and request.user.perfil.empleado:
            aprobador = request.user.perfil.empleado
        elif solicitud.aprobador:
            aprobador = solicitud.aprobador

        if not aprobador:
            return Response(
                {"detail": "No se pudo determinar el aprobador."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            services.aprobar_solicitud(solicitud, aprobador, comentario)
            return Response(SolicitudAusenciaSerializer(solicitud).data)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="rechazar")
    def rechazar(self, request, pk=None):
        """Rechaza la solicitud."""
        solicitud = self.get_object()
        comentario = request.data.get("comentario", "")

        aprobador = None
        if hasattr(request.user, "perfil") and request.user.perfil.empleado:
            aprobador = request.user.perfil.empleado
        elif solicitud.aprobador:
            aprobador = solicitud.aprobador

        try:
            services.rechazar_solicitud(solicitud, aprobador, comentario)
            return Response(SolicitudAusenciaSerializer(solicitud).data)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="cancelar")
    def cancelar(self, request, pk=None):
        """Cancela la solicitud."""
        solicitud = self.get_object()
        motivo = request.data.get("motivo", "")

        try:
            services.cancelar_solicitud(solicitud, request.user, motivo)
            return Response(SolicitudAusenciaSerializer(solicitud).data)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"], url_path="pendientes")
    def pendientes(self, request):
        """Solicitudes pendientes de aprobación por el usuario actual."""
        qs = self.get_queryset().filter(estatus="pendiente")
        return Response(SolicitudAusenciaListSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="calendario")
    def calendario(self, request):
        """
        Devuelve las solicitudes aprobadas en formato calendario.
        Query params: fecha_desde, fecha_hasta
        """
        from datetime import datetime

        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")

        qs = self.get_queryset().filter(
            estatus__in=["aprobada", "en_disfrute"],
        )

        if fecha_desde:
            try:
                fd = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
                qs = qs.filter(fecha_fin__gte=fd)
            except ValueError:
                pass
        if fecha_hasta:
            try:
                fh = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
                qs = qs.filter(fecha_inicio__lte=fh)
            except ValueError:
                pass

        data = []
        for sol in qs:
            data.append({
                "id": sol.id,
                "title": f"{sol.empleado.nombre_completo} - {sol.tipo.nombre}",
                "start": sol.fecha_inicio.isoformat(),
                "end": (sol.fecha_fin + timedelta(days=1)).isoformat(),
                "empleado": sol.empleado.nombre_completo,
                "tipo": sol.tipo.nombre,
                "categoria": sol.tipo.categoria,
                "dias": float(sol.dias_solicitados),
            })

        return Response(data)


# ═══════════════════════════════════════════════════════════
#  MOVIMIENTOS DE SALDO (solo lectura)
# ═══════════════════════════════════════════════════════════

class MovimientoSaldoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovimientoSaldoVacaciones.objects.select_related(
        "saldo", "saldo__empleado", "solicitud", "usuario"
    ).all()
    serializer_class = MovimientoSaldoSerializer
    permission_classes = [IsAuthenticated, EsRRHH]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["saldo", "tipo"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, "perfil") and user.perfil.empresa:
            return qs.filter(saldo__empleado__empresa=user.perfil.empresa)
        return qs.none()
        
    @action(detail=False, methods=["get"], url_path="mis-movimientos")
    def mis_movimientos(self, request):
        """
        Historial de movimientos de saldo del empleado logueado. Paginado.
        Query params:
          - anio (int, opcional)
          - page (int, opcional, default 1)
        """
        perfil = getattr(request.user, "perfil", None)
        empleado = getattr(perfil, "empleado", None) if perfil else None

        if not empleado:
            return Response(
                {"detail": "Tu usuario no está vinculado a un empleado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = (
            MovimientoSaldoVacaciones.objects
            .filter(saldo__empleado=empleado)
            .select_related("saldo", "solicitud")
            .order_by("-created_at")
        )

        # Filtro por año
        anio = request.query_params.get("anio")
        if anio:
            try:
                qs = qs.filter(saldo__anio=int(anio))
            except (ValueError, TypeError):
                pass

        # Paginación
        try:
            page = int(request.query_params.get("page", 1))
        except (ValueError, TypeError):
            page = 1
        page_size = 10
        start = (page - 1) * page_size
        end = start + page_size
        total = qs.count()

        items = qs[start:end]
        serializer = MovimientoSaldoSerializer(items, many=True)

        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "results": serializer.data,
        })
        