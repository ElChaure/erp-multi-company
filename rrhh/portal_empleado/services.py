"""
Servicios del Portal del Empleado (API JWT).

Lógica de negocio compartida entre las vistas de la API.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q

from rrhh.models import (
    NominaEmpleado,
    SaldoVacaciones,
    MovimientoSaldoVacaciones,
    SolicitudAusencia,
    TipoAusencia,
)


# ═══════════════════════════════════════════════════════════
# HELPERS GENERALES
# ═══════════════════════════════════════════════════════════

def get_empleado_de_request(request):
    """
    Devuelve el Empleado del usuario logueado vía CuentaEmpleado.
    Retorna None si no tiene cuenta.
    """
    cuenta = getattr(request.user, "cuenta_empleado", None)
    if not cuenta:
        return None
    return cuenta.empleado


# ═══════════════════════════════════════════════════════════
# RECIBOS
# ═══════════════════════════════════════════════════════════

def get_recibos_del_empleado(empleado, anio=None):
    """
    Recibos visibles para el empleado.

    Solo se muestran los de periodos CERRADOS (los aprobados todavía
    pueden cambiar, los abiertos ni siquiera están completos).

    Orden: fecha_pago descendente (más reciente primero).
    """
    qs = (
        NominaEmpleado.objects
        .filter(empleado=empleado, periodo__estatus="cerrado")
        .select_related("periodo", "periodo__empresa")
        .prefetch_related("detalles")
        .order_by("-periodo__fecha_pago", "-id")
    )

    if anio:
        qs = qs.filter(periodo__anio=anio)

    return qs


def get_anios_con_recibos(empleado):
    """Lista de años con recibos cerrados (descendente)."""
    return list(
        NominaEmpleado.objects
        .filter(empleado=empleado, periodo__estatus="cerrado")
        .values_list("periodo__anio", flat=True)
        .distinct()
        .order_by("-periodo__anio")
    )


def get_recibo_del_empleado(empleado, nomina_id):
    """
    Devuelve un recibo específico, validando que sea del empleado
    y que el periodo esté cerrado.
    """
    return NominaEmpleado.objects.select_related(
        "periodo", "periodo__empresa", "empleado"
    ).prefetch_related("detalles").get(
        pk=nomina_id,
        empleado=empleado,
        periodo__estatus="cerrado",
    )


# ═══════════════════════════════════════════════════════════
# VACACIONES — SALDOS
# ═══════════════════════════════════════════════════════════

def get_saldos_del_empleado(empleado, anio=None):
    """Saldos de vacaciones del empleado, ordenados por año descendente."""
    qs = SaldoVacaciones.objects.filter(empleado=empleado)
    if anio:
        qs = qs.filter(anio=anio)
    return qs.order_by("-anio")


def get_anios_con_saldo(empleado):
    """Lista de años con saldo registrado (descendente)."""
    return list(
        SaldoVacaciones.objects
        .filter(empleado=empleado)
        .values_list("anio", flat=True)
        .distinct()
        .order_by("-anio")
    )


# ═══════════════════════════════════════════════════════════
# VACACIONES — MOVIMIENTOS
# ═══════════════════════════════════════════════════════════

def get_movimientos_del_empleado(empleado, anio=None):
    """
    Historial de movimientos de saldo de vacaciones.
    Filtro opcional por año del saldo.
    """
    qs = (
        MovimientoSaldoVacaciones.objects
        .filter(saldo__empleado=empleado)
        .select_related("saldo", "solicitud", "usuario")
        .order_by("-created_at")
    )

    if anio:
        qs = qs.filter(saldo__anio=anio)

    return qs


# ═══════════════════════════════════════════════════════════
# VACACIONES — SOLICITUDES
# ═══════════════════════════════════════════════════════════

def get_solicitudes_del_empleado(empleado, estatus=None):
    """Solicitudes de ausencia del empleado."""
    qs = (
        SolicitudAusencia.objects
        .filter(empleado=empleado)
        .select_related("tipo", "aprobador")
        .order_by("-fecha_solicitud")
    )

    if estatus:
        qs = qs.filter(estatus=estatus)

    return qs


def get_solicitud_del_empleado(empleado, solicitud_id):
    """Devuelve una solicitud específica del empleado."""
    return SolicitudAusencia.objects.select_related(
        "tipo", "aprobador"
    ).get(pk=solicitud_id, empleado=empleado)


# ═══════════════════════════════════════════════════════════
# VACACIONES — HELPERS DE CÁLCULO
# ═══════════════════════════════════════════════════════════

def get_tipo_vacaciones(empresa):
    """
    Devuelve el TipoAusencia de categoría 'vacaciones'.
    Prioriza el de la empresa sobre los globales (empresa=None).
    """
    return (
        TipoAusencia.objects
        .filter(
            Q(empresa=empresa) | Q(empresa__isnull=True),
            categoria="vacaciones",
            activo=True,
        )
        .order_by("-empresa_id")
        .first()
    )


def calcular_dias_habiles(fecha_inicio, fecha_fin):
    """Cuenta días hábiles (lunes a viernes) entre dos fechas inclusive."""
    if not fecha_inicio or not fecha_fin or fecha_inicio > fecha_fin:
        return 0
    dias = 0
    actual = fecha_inicio
    while actual <= fecha_fin:
        if actual.weekday() < 5:
            dias += 1
        actual += timedelta(days=1)
    return dias