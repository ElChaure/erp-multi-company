"""
Vistas de datos del Portal del Empleado (API JWT).

Endpoints:
 GET    /api/v1/empleado/recibos/                              → Lista recibos
 GET    /api/v1/empleado/recibos/<id>/                         → Detalle recibo
 GET    /api/v1/empleado/recibos/<id>/pdf/                     → PDF recibo
 GET    /api/v1/empleado/vacaciones/saldos/                    → Saldos
 GET    /api/v1/empleado/vacaciones/movimientos/               → Movimientos
 GET    /api/v1/empleado/vacaciones/solicitudes/               → Mis solicitudes
 POST   /api/v1/empleado/vacaciones/solicitudes/               → Crear solicitud
 GET    /api/v1/empleado/vacaciones/solicitudes/<id>/          → Detalle
 POST   /api/v1/empleado/vacaciones/solicitudes/<id>/cancelar/ → Cancelar
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CuentaEmpleado
from .permissions import IsCuentaEmpleado
from .serializers import (
    CuentaEmpleadoSerializer,
    PerfilEmpleadoSerializer,
    PerfilEmpleadoUpdateSerializer,
    ReciboListaSerializer,
    ReciboDetalleSerializer,
    SaldoVacacionesSerializer,
    MovimientoVacacionesSerializer,
    SolicitudAusenciaPortalSerializer,
    CrearSolicitudSerializer,
)
from . import services


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _get_cuenta(request):
    """Devuelve la CuentaEmpleado del usuario logueado (o None)."""
    return getattr(request.user, "cuenta_empleado", None)


def _get_empleado(request):
    """Devuelve el Empleado del usuario logueado (o None)."""
    cuenta = _get_cuenta(request)
    return cuenta.empleado if cuenta else None


# ═══════════════════════════════════════════════════════════
# PERFIL / CUENTA
# ═══════════════════════════════════════════════════════════

class MiCuentaView(APIView):
    """
    GET /api/v1/empleado/mi-cuenta/
    Devuelve los datos de la cuenta logueada.
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request):
        cuenta = _get_cuenta(request)
        return Response(CuentaEmpleadoSerializer(cuenta).data)


class MiPerfilView(RetrieveUpdateAPIView):
    """
    GET   /api/v1/empleado/perfil/ → Ver datos del empleado
    PATCH /api/v1/empleado/perfil/ → Actualizar teléfono, dirección, email
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get_object(self):
        return _get_empleado(self.request)

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return PerfilEmpleadoUpdateSerializer
        return PerfilEmpleadoSerializer


# ═══════════════════════════════════════════════════════════
# RECIBOS
# ═══════════════════════════════════════════════════════════

class MisRecibosView(APIView):
    """
    GET /api/v1/empleado/recibos/
    Lista paginada de recibos de nómina del empleado logueado.

    Query params:
     - anio: filtra por año (ej: ?anio=2026)
     - page: número de página
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request):
        empleado = _get_empleado(request)

        anio_str = request.query_params.get("anio", "").strip()
        anio = int(anio_str) if anio_str.isdigit() else None

        qs = services.get_recibos_del_empleado(empleado, anio=anio)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ReciboListaSerializer(page, many=True)

        # Datos extra para el frontend (filtros)
        anios_disponibles = services.get_anios_con_recibos(empleado)

        response_data = paginator.get_paginated_response(serializer.data).data
        response_data["anios_disponibles"] = anios_disponibles
        response_data["anio_filtro"] = anio

        return Response(response_data)


class MiReciboDetalleView(APIView):
    """
    GET /api/v1/empleado/recibos/<id>/
    Detalle completo del recibo (con todas las líneas).
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request, recibo_id):
        empleado = _get_empleado(request)
        try:
            recibo = services.get_recibo_del_empleado(empleado, recibo_id)
        except Exception:
            return Response(
                {"detail": "Recibo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ReciboDetalleSerializer(recibo)
        return Response(serializer.data)


class MiReciboPDFView(APIView):
    """
    GET /api/v1/empleado/recibos/<id>/pdf/
    Devuelve el PDF del recibo.

    Usa el generador existente rrhh/nomina/pdf/recibo.py
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request, recibo_id):
        empleado = _get_empleado(request)
        try:
            recibo = services.get_recibo_del_empleado(empleado, recibo_id)
        except Exception:
            return Response(
                {"detail": "Recibo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Importar el generador de PDF existente
        try:
            from rrhh.nomina.pdf.recibo import generar_pdf_recibo
        except ImportError:
            return Response(
                {"detail": "El generador de PDF no está disponible."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        # Generar el PDF
        try:
            pdf_buffer = generar_pdf_recibo(recibo)
        except Exception as e:
            return Response(
                {"detail": f"Error al generar PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        filename = (
            f"recibo_{empleado.numero_empleado}_"
            f"{recibo.periodo.anio}_{recibo.periodo.numero_periodo}.pdf"
        )

        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=filename,
            content_type="application/pdf",
        )


# ═══════════════════════════════════════════════════════════
# VACACIONES — SALDOS
# ═══════════════════════════════════════════════════════════

class MisVacacionesSaldosView(APIView):
    """
    GET /api/v1/empleado/vacaciones/saldos/
    Saldos de vacaciones por año (todos los años del empleado).
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request):
        empleado = _get_empleado(request)

        anio_str = request.query_params.get("anio", "").strip()
        anio = int(anio_str) if anio_str.isdigit() else None

        saldos = services.get_saldos_del_empleado(empleado, anio=anio)
        serializer = SaldoVacacionesSerializer(saldos, many=True)

        return Response({
            "saldos": serializer.data,
            "anios_disponibles": services.get_anios_con_saldo(empleado),
        })


# ═══════════════════════════════════════════════════════════
# VACACIONES — MOVIMIENTOS
# ═══════════════════════════════════════════════════════════

class MisVacacionesMovimientosView(APIView):
    """
    GET /api/v1/empleado/vacaciones/movimientos/
    Historial de movimientos de saldo (asignaciones, tomas, ajustes, etc).

    Query params:
     - anio: filtra por año del saldo
     - page: número de página
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request):
        empleado = _get_empleado(request)

        anio_str = request.query_params.get("anio", "").strip()
        anio = int(anio_str) if anio_str.isdigit() else None

        qs = services.get_movimientos_del_empleado(empleado, anio=anio)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = MovimientoVacacionesSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ═══════════════════════════════════════════════════════════
# VACACIONES — SOLICITUDES
# ═══════════════════════════════════════════════════════════

class MisSolicitudesView(APIView):
    """
    GET  /api/v1/empleado/vacaciones/solicitudes/ → Lista
    POST /api/v1/empleado/vacaciones/solicitudes/ → Crear
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request):
        """Lista paginada de solicitudes del empleado."""
        empleado = _get_empleado(request)

        estatus = request.query_params.get("estatus", "").strip() or None

        qs = services.get_solicitudes_del_empleado(empleado, estatus=estatus)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = SolicitudAusenciaPortalSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Crea una nueva solicitud de vacaciones."""
        empleado = _get_empleado(request)

        serializer = CrearSolicitudSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fecha_inicio = serializer.validated_data["fecha_inicio"]
        fecha_fin = serializer.validated_data["fecha_fin"]
        motivo = serializer.validated_data.get("motivo", "").strip() or "Solicitud de vacaciones"

        # Obtener el tipo de ausencia "vacaciones"
        tipo = services.get_tipo_vacaciones(empleado.empresa)
        if not tipo:
            return Response(
                {"detail": "No hay un tipo de ausencia de vacaciones configurado. "
                           "Contactá a RRHH."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calcular días hábiles
        dias_habiles = services.calcular_dias_habiles(fecha_inicio, fecha_fin)
        if dias_habiles <= 0:
            return Response(
                {"fecha_inicio": ["El rango no contiene días hábiles."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delegar validación al service existente
        # (usa la misma lógica que el portal Django)
        try:
            from rrhh.ausencias.services import validar_solicitud
            validar_solicitud(
                empleado=empleado,
                tipo=tipo,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                dias_solicitados=dias_habiles,
            )
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else [str(e)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Crear la solicitud
        from datetime import timedelta
        solicitud = SolicitudAusencia.objects.create(
            empleado=empleado,
            tipo=tipo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            dias_solicitados=dias_habiles,
            dias_calendario=(fecha_fin - fecha_inicio).days + 1,
            fecha_reincorporacion=fecha_fin + timedelta(days=1),
            motivo=motivo,
            estatus="pendiente",
        )

        return Response(
            SolicitudAusenciaPortalSerializer(solicitud).data,
            status=status.HTTP_201_CREATED,
        )


class MiSolicitudDetalleView(APIView):
    """
    GET /api/v1/empleado/vacaciones/solicitudes/<id>/
    Detalle de una solicitud del empleado.
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def get(self, request, solicitud_id):
        empleado = _get_empleado(request)
        try:
            solicitud = services.get_solicitud_del_empleado(empleado, solicitud_id)
        except Exception:
            return Response(
                {"detail": "Solicitud no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(SolicitudAusenciaPortalSerializer(solicitud).data)


class MiSolicitudCancelarView(APIView):
    """
    POST /api/v1/empleado/vacaciones/solicitudes/<id>/cancelar/
    Cancela una solicitud propia (solo si está pendiente o aprobada).
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]

    def post(self, request, solicitud_id):
        empleado = _get_empleado(request)
        try:
            solicitud = services.get_solicitud_del_empleado(empleado, solicitud_id)
        except Exception:
            return Response(
                {"detail": "Solicitud no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validar que se pueda cancelar
        if solicitud.estatus not in ("pendiente", "aprobada"):
            return Response(
                {"detail": f"No se puede cancelar una solicitud en estado "
                           f"'{solicitud.get_estatus_display()}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        motivo = request.data.get("motivo", "").strip() or "Cancelada por el empleado"

        try:
            from rrhh.ausencias.services import cancelar_solicitud
            cancelar_solicitud(solicitud, usuario=request.user, motivo=motivo)
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else [str(e)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            SolicitudAusenciaPortalSerializer(solicitud).data,
            status=status.HTTP_200_OK,
        )