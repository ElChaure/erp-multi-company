"""
Endpoints de reportes de nómina.
"""
from datetime import date, datetime
from decimal import Decimal

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from ..permissions import EsRRHH
from . import nomina_reportes
from . import maestros_reportes

def _parse_bool(valor):
    """Convierte string 'true'/'false' a bool."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return valor
    return valor.lower() in ("true", "1", "yes", "si", "sí")

# ═══════════════════════════════════════════════════════════
#  PARÁMETROS COMUNES
# ═══════════════════════════════════════════════════════════

PARAM_FECHA_DESDE = OpenApiParameter(
    name="fecha_desde",
    type=OpenApiTypes.DATE,
    location=OpenApiParameter.QUERY,
    description="Fecha de inicio del rango (formato YYYY-MM-DD)",
    required=False,
)

PARAM_FECHA_HASTA = OpenApiParameter(
    name="fecha_hasta",
    type=OpenApiTypes.DATE,
    location=OpenApiParameter.QUERY,
    description="Fecha de fin del rango (formato YYYY-MM-DD)",
    required=False,
)

PARAM_ESTATUS = OpenApiParameter(
    name="estatus",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description="Filtrar por estatus. Puedes pasar varios separados por coma: 'calculado,aprobado'",
    required=False,
    enum=["abierto", "calculado", "aprobado", "pagado", "cerrado"],
)

PARAM_EMPRESA_ID = OpenApiParameter(
    name="empresa_id",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description="ID de la empresa (solo para superadmins)",
    required=False,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _parse_fecha(valor):
    """Convierte string a date."""
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_estatus(valor):
    """Parsea el estatus (puede ser string o lista separada por comas)."""
    if not valor:
        return None
    if "," in valor:
        return valor.split(",")
    return valor


def _empresa_id(request):
    """Obtiene la empresa del usuario (o de query param si es superadmin)."""
    # Superadmin puede especificar empresa_id
    if request.user.is_superuser:
        empresa_id = request.query_params.get("empresa_id")
        if empresa_id:
            return int(empresa_id)
        # Si no especifica, usar la primera empresa
        from ..models import Empresa
        empresa = Empresa.objects.first()
        return empresa.id if empresa else None

    # Usuario normal: su empresa
    if hasattr(request.user, "perfil") and request.user.perfil.empresa:
        return request.user.perfil.empresa.id

    return None


def _decimal_to_float(obj):
    """Convierte Decimal a float recursivamente."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_decimal_to_float(item) for item in obj]
    elif isinstance(obj, date):
        return obj.isoformat()
    return obj


# ═══════════════════════════════════════════════════════════
#  REPORTES
# ═══════════════════════════════════════════════════════════

@extend_schema(
    summary="Costo de nómina por departamento",
    description="Agrupa los costos de nómina por departamento en un rango de fechas.",
    parameters=[
        PARAM_EMPRESA_ID,
        PARAM_FECHA_DESDE,
        PARAM_FECHA_HASTA,
        PARAM_ESTATUS,
        OpenApiParameter(
            name="departamento_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Filtrar por un departamento específico",
            required=False,
        ),
    ],
    tags=["Reportes de Nómina"],
)
class CostoPorDepartamentoView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        empresa_id = _empresa_id(request)
        if not empresa_id:
            return Response(
                {"detail": "No hay empresa asociada al usuario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = nomina_reportes.costo_por_departamento(
            empresa_id=empresa_id,
            fecha_desde=_parse_fecha(request.query_params.get("fecha_desde")),
            fecha_hasta=_parse_fecha(request.query_params.get("fecha_hasta")),
            estatus=_parse_estatus(request.query_params.get("estatus")),
            departamento_id=request.query_params.get("departamento_id"),
        )

        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Costo de nómina por cargo",
    description="Agrupa los costos de nómina por cargo en un rango de fechas.",
    parameters=[
        PARAM_EMPRESA_ID,
        PARAM_FECHA_DESDE,
        PARAM_FECHA_HASTA,
        PARAM_ESTATUS,
        OpenApiParameter(
            name="cargo_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Filtrar por un cargo específico",
            required=False,
        ),
    ],
    tags=["Reportes de Nómina"],
)
class CostoPorCargoView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        empresa_id = _empresa_id(request)
        if not empresa_id:
            return Response(
                {"detail": "No hay empresa asociada al usuario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = nomina_reportes.costo_por_cargo(
            empresa_id=empresa_id,
            fecha_desde=_parse_fecha(request.query_params.get("fecha_desde")),
            fecha_hasta=_parse_fecha(request.query_params.get("fecha_hasta")),
            estatus=_parse_estatus(request.query_params.get("estatus")),
            cargo_id=request.query_params.get("cargo_id"),
        )

        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Retenciones de ISLR por empleado",
    description="Retenciones de ISLR aplicadas a cada empleado en un rango de fechas.",
    parameters=[
        PARAM_EMPRESA_ID,
        PARAM_FECHA_DESDE,
        PARAM_FECHA_HASTA,
        PARAM_ESTATUS,
        OpenApiParameter(
            name="empleado_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Filtrar por un empleado específico",
            required=False,
        ),
    ],
    tags=["Reportes de Nómina"],
)
class RetencionesISLRView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        empresa_id = _empresa_id(request)
        if not empresa_id:
            return Response(
                {"detail": "No hay empresa asociada al usuario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = nomina_reportes.retenciones_islr(
            empresa_id=empresa_id,
            fecha_desde=_parse_fecha(request.query_params.get("fecha_desde")),
            fecha_hasta=_parse_fecha(request.query_params.get("fecha_hasta")),
            estatus=_parse_estatus(request.query_params.get("estatus")),
            empleado_id=request.query_params.get("empleado_id"),
        )

        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Aportes a entes (IVSS, RPE, BANAVIH, INCES, LOPCYMAT)",
    description="Aportes obreros y patronales agrupados por concepto.",
    parameters=[
        PARAM_EMPRESA_ID,
        PARAM_FECHA_DESDE,
        PARAM_FECHA_HASTA,
        PARAM_ESTATUS,
    ],
    tags=["Reportes de Nómina"],
)
class AportesEntesView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        empresa_id = _empresa_id(request)
        if not empresa_id:
            return Response(
                {"detail": "No hay empresa asociada al usuario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = nomina_reportes.aportes_a_entes(
            empresa_id=empresa_id,
            fecha_desde=_parse_fecha(request.query_params.get("fecha_desde")),
            fecha_hasta=_parse_fecha(request.query_params.get("fecha_hasta")),
            estatus=_parse_estatus(request.query_params.get("estatus")),
        )

        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Resumen por periodo de nómina",
    description="Totales de cada periodo de nómina en un rango de fechas.",
    parameters=[
        PARAM_EMPRESA_ID,
        PARAM_FECHA_DESDE,
        PARAM_FECHA_HASTA,
        PARAM_ESTATUS,
        OpenApiParameter(
            name="tipo",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filtrar por tipo de periodo",
            required=False,
            enum=["semanal", "catorcenal", "quincenal", "mensual"],
        ),
    ],
    tags=["Reportes de Nómina"],
)
class ResumenPorPeriodoView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        empresa_id = _empresa_id(request)
        if not empresa_id:
            return Response(
                {"detail": "No hay empresa asociada al usuario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = nomina_reportes.resumen_por_periodo(
            empresa_id=empresa_id,
            fecha_desde=_parse_fecha(request.query_params.get("fecha_desde")),
            fecha_hasta=_parse_fecha(request.query_params.get("fecha_hasta")),
            estatus=_parse_estatus(request.query_params.get("estatus")),
            tipo=request.query_params.get("tipo"),
        )

        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Resumen consolidado de nómina",
    description="Totales generales del rango seleccionado.",
    parameters=[
        PARAM_EMPRESA_ID,
        PARAM_FECHA_DESDE,
        PARAM_FECHA_HASTA,
        PARAM_ESTATUS,
    ],
    tags=["Reportes de Nómina"],
)
class ResumenConsolidadoView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        empresa_id = _empresa_id(request)
        if not empresa_id:
            return Response(
                {"detail": "No hay empresa asociada al usuario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = nomina_reportes.resumen_consolidado(
            empresa_id=empresa_id,
            fecha_desde=_parse_fecha(request.query_params.get("fecha_desde")),
            fecha_hasta=_parse_fecha(request.query_params.get("fecha_hasta")),
            estatus=_parse_estatus(request.query_params.get("estatus")),
        )

        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Evolución mensual del costo de nómina",
    description="Totales agrupados por mes para los últimos N meses.",
    parameters=[
        PARAM_EMPRESA_ID,
        PARAM_ESTATUS,
        OpenApiParameter(
            name="meses",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Cantidad de meses hacia atrás a incluir",
            required=False,
            default=12,
        ),
    ],
    tags=["Reportes de Nómina"],
)
class EvolucionMensualView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        empresa_id = _empresa_id(request)
        if not empresa_id:
            return Response(
                {"detail": "No hay empresa asociada al usuario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        meses = int(request.query_params.get("meses", 12))

        data = nomina_reportes.evolucion_mensual(
            empresa_id=empresa_id,
            meses=meses,
            estatus=_parse_estatus(request.query_params.get("estatus")),
        )

        return Response(_decimal_to_float(data))
        



# ═══════════════════════════════════════════════════════════
#  REPORTES MAESTROS
# ═══════════════════════════════════════════════════════════

@extend_schema(
    summary="Reporte de Empresas",
    description="Listado maestro de empresas con contadores de sedes, departamentos y empleados.",
    parameters=[
        OpenApiParameter(name="empresa_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="tipo", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         enum=["matriz", "filial", "holding", "externa"]),
        OpenApiParameter(name="activa", type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteEmpresasView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_empresas(
            empresa_id=_empresa_id(request) if not request.user.is_superuser else request.query_params.get("empresa_id"),
            tipo=request.query_params.get("tipo"),
            activa=_parse_bool(request.query_params.get("activa")),
        )
        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Reporte de Sedes",
    description="Listado maestro de sedes con filtros por empresa y tipo.",
    parameters=[
        OpenApiParameter(name="empresa_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="sede_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="tipo", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         enum=["principal", "sucursal", "almacen", "planta", "oficina"]),
        OpenApiParameter(name="activa", type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteSedesView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_sedes(
            empresa_id=_empresa_id(request) if not request.user.is_superuser else request.query_params.get("empresa_id"),
            tipo=request.query_params.get("tipo"),
            activa=_parse_bool(request.query_params.get("activa")),
            sede_id=request.query_params.get("sede_id"),
        )
        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Reporte de Departamentos",
    description="Listado maestro de departamentos con jerarquía, responsable y contadores.",
    parameters=[
        OpenApiParameter(name="empresa_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="departamento_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="padre_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="activo", type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteDepartamentosView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_departamentos(
            empresa_id=_empresa_id(request) if not request.user.is_superuser else request.query_params.get("empresa_id"),
            activo=_parse_bool(request.query_params.get("activo")),
            padre_id=request.query_params.get("padre_id"),
            departamento_id=request.query_params.get("departamento_id"),
        )
        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Reporte de Cargos",
    description="Listado maestro de cargos con rango salarial y empleados asignados.",
    parameters=[
        OpenApiParameter(name="cargo_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="activo", type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteCargosView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_cargos(
            activo=_parse_bool(request.query_params.get("activo")),
            cargo_id=request.query_params.get("cargo_id"),
        )
        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Reporte de Empleados",
    description="Listado maestro completo de empleados con múltiples filtros.",
    parameters=[
        OpenApiParameter(name="empresa_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="empleado_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="estatus", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         description="Uno o varios separados por coma: activo,licencia",
                         enum=["activo", "baja", "licencia", "vacaciones"]),
        OpenApiParameter(name="departamento_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="cargo_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="sede_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="nacionalidad", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         enum=["V", "E", "P"]),
        OpenApiParameter(name="tipo_contrato", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="fecha_ingreso_desde", type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="fecha_ingreso_hasta", type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteEmpleadosView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_empleados(
            empresa_id=_empresa_id(request) if not request.user.is_superuser else request.query_params.get("empresa_id"),
            estatus=_parse_estatus(request.query_params.get("estatus")),
            departamento_id=request.query_params.get("departamento_id"),
            cargo_id=request.query_params.get("cargo_id"),
            sede_id=request.query_params.get("sede_id"),
            nacionalidad=request.query_params.get("nacionalidad"),
            tipo_contrato=request.query_params.get("tipo_contrato"),
            fecha_ingreso_desde=_parse_fecha(request.query_params.get("fecha_ingreso_desde")),
            fecha_ingreso_hasta=_parse_fecha(request.query_params.get("fecha_ingreso_hasta")),
            empleado_id=request.query_params.get("empleado_id"),
        )
        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Reporte de Conceptos de Nómina",
    description="Listado maestro de conceptos de nómina con tipo, naturaleza y fórmulas.",
    parameters=[
        OpenApiParameter(name="empresa_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="concepto_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="tipo", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         enum=["percepcion", "deduccion", "aporte_patronal"]),
        OpenApiParameter(name="naturaleza", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         enum=["gravado", "exento", "mixto"]),
        OpenApiParameter(name="activo", type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteConceptosView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_conceptos(
            empresa_id=_empresa_id(request) if not request.user.is_superuser else request.query_params.get("empresa_id"),
            tipo=request.query_params.get("tipo"),
            activo=_parse_bool(request.query_params.get("activo")),
            naturaleza=request.query_params.get("naturaleza"),
            concepto_id=request.query_params.get("concepto_id"),
        )
        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Reporte de Parámetros de Nómina",
    description="Listado maestro de parámetros por empresa y año.",
    parameters=[
        OpenApiParameter(name="empresa_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="anio", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="activo", type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteParametrosView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_parametros(
            empresa_id=_empresa_id(request) if not request.user.is_superuser else request.query_params.get("empresa_id"),
            anio=request.query_params.get("anio"),
            activo=_parse_bool(request.query_params.get("activo")),
        )
        return Response(_decimal_to_float(data))


@extend_schema(
    summary="Reporte de Incidencias",
    description="Listado maestro de incidencias de nómina.",
    parameters=[
        OpenApiParameter(name="empresa_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="empleado_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="periodo_id", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="tipo", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         description="Uno o varios separados por coma"),
        OpenApiParameter(name="estatus", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False,
                         description="Uno o varios separados por coma: pendiente,aprobada"),
        OpenApiParameter(name="fecha_desde", type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, required=False),
        OpenApiParameter(name="fecha_hasta", type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, required=False),
    ],
    tags=["Reportes Maestros"],
)
class ReporteIncidenciasView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    def get(self, request):
        data = maestros_reportes.reporte_incidencias(
            empresa_id=_empresa_id(request) if not request.user.is_superuser else request.query_params.get("empresa_id"),
            tipo=_parse_estatus(request.query_params.get("tipo")),
            estatus=_parse_estatus(request.query_params.get("estatus")),
            fecha_desde=_parse_fecha(request.query_params.get("fecha_desde")),
            fecha_hasta=_parse_fecha(request.query_params.get("fecha_hasta")),
            empleado_id=request.query_params.get("empleado_id"),
            periodo_id=request.query_params.get("periodo_id"),
        )
        return Response(_decimal_to_float(data))