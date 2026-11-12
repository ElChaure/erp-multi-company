"""
Motor de cálculo de vacaciones (LOTTT Art. 190-192).

Soporta:
    - Cálculo base LOTTT (15 días + 1 por año, tope 30)
    - Contrato colectivo con reglas más ventajosas
    - Vacaciones fraccionadas (al egreso)
    - Vencimiento configurable
    - Vacaciones colectivas

Referencias:
    - LOTTT Art. 190, 191, 192
    - Código Civil (para cálculo de fracciones)
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .constants import (
    DIAS_BASE_VACACIONES,
    DIAS_BASE_BONO_VACACIONAL,
    DIAS_MAX_VACACIONES,
    DIAS_MAX_BONO_VACACIONAL,
    INCREMENTO_ANUAL,
    MESES_VENCIMIENTO_DEFAULT,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _r2(valor):
    """Redondea a 2 decimales."""
    if valor is None:
        return Decimal("0")
    return Decimal(str(valor)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def calcular_anios_antiguedad(fecha_ingreso, fecha_referencia=None):
    """Años completos entre la fecha de ingreso y la referencia."""
    if fecha_referencia is None:
        fecha_referencia = date.today()
    anios = fecha_referencia.year - fecha_ingreso.year
    if (fecha_referencia.month, fecha_referencia.day) < (
        fecha_ingreso.month, fecha_ingreso.day
    ):
        anios -= 1
    return max(anios, 0)


def calcular_meses_fraccion(fecha_desde, fecha_hasta):
    """
    Meses completos entre dos fechas (para fracciones de vacaciones).
    """
    if fecha_desde > fecha_hasta:
        return 0
    meses = (fecha_hasta.year - fecha_desde.year) * 12
    meses += fecha_hasta.month - fecha_desde.month
    if fecha_hasta.day < fecha_desde.day:
        meses -= 1
    return max(meses, 0)


def dias_habiles_entre(fecha_inicio, fecha_fin):
    """Cuenta días hábiles (lunes a viernes) entre dos fechas inclusive."""
    if fecha_inicio > fecha_fin:
        return 0
    dias = 0
    fecha = fecha_inicio
    while fecha <= fecha_fin:
        if fecha.weekday() < 5:
            dias += 1
        fecha += timedelta(days=1)
    return dias


# ═══════════════════════════════════════════════════════════
#  CÁLCULO BASE LOTTT
# ═══════════════════════════════════════════════════════════

def calcular_dias_vacaciones(anios_antiguedad, config=None):
    """
    Días de vacaciones según antigüedad.

    LOTTT Art. 190:
        - Primer año: 15 días hábiles.
        - Años siguientes: +1 día por año, hasta 30.

    Si hay contrato colectivo, usa los valores configurados.
    """
    if config and config.aplica_contrato_colectivo:
        base = config.valor_dias_vacaciones
        maximo = config.valor_dias_max_vacaciones
        incremento = config.valor_incremento_anual_vacaciones
    else:
        base = DIAS_BASE_VACACIONES
        maximo = DIAS_MAX_VACACIONES
        incremento = INCREMENTO_ANUAL

    if anios_antiguedad < 1:
        return base
    return min(base + (anios_antiguedad - 1) * incremento, maximo)


def calcular_dias_bono_vacacional(anios_antiguedad, config=None):
    """
    Días de bono vacacional según antigüedad.

    LOTTT Art. 192:
        - Primer año: 15 días.
        - Años siguientes: +1 día por año, hasta 30.
    """
    if config and config.aplica_contrato_colectivo:
        base = config.valor_dias_bono_vacacional
        maximo = config.valor_dias_max_bono
        incremento = config.valor_incremento_anual_bono
    else:
        base = DIAS_BASE_BONO_VACACIONAL
        maximo = DIAS_MAX_BONO_VACACIONAL
        incremento = INCREMENTO_ANUAL

    if anios_antiguedad < 1:
        return base
    return min(base + (anios_antiguedad - 1) * incremento, maximo)


# ═══════════════════════════════════════════════════════════
#  CÁLCULO ANUAL (para generar saldos)
# ═══════════════════════════════════════════════════════════

def calcular_saldo_anual(empleado, anio, config=None):
    """
    Calcula el saldo de vacaciones que corresponde a un empleado
    para un año específico.

    Args:
        empleado: instancia de Empleado
        anio: año a calcular (int)
        config: instancia de ConfiguracionVacaciones (opcional)

    Returns:
        dict con:
            - anio
            - anios_antiguedad (a 31/12 del año)
            - dias_derecho
            - dias_bono_vacacional
            - fecha_causacion
            - fecha_vencimiento
            - prorrateado
            - meses_trabajados
    """
    from rrhh.models import ConfiguracionVacaciones

    if config is None:
        config = ConfiguracionVacaciones.objects.filter(
            empresa=empleado.empresa,
        ).first()

    fecha_ingreso = empleado.fecha_ingreso
    fecha_cierre = date(anio, 12, 31)

    # Años de antigüedad al cierre del año
    anios = calcular_anios_antiguedad(fecha_ingreso, fecha_cierre)

    # Días base
    dias_derecho = Decimal(str(calcular_dias_vacaciones(anios, config)))
    dias_bono = Decimal(str(calcular_dias_bono_vacacional(anios, config)))

    # Prorratear si ingresó durante el año
    prorrateado = False
    meses_trabajados = 12

    if fecha_ingreso.year == anio:
        meses_trabajados = 12 - fecha_ingreso.month + 1
        dias_derecho = _r2(dias_derecho * meses_trabajados / 12)
        dias_bono = _r2(dias_bono * meses_trabajados / 12)
        prorrateado = True

    # Fecha de causación (31/12 del año)
    fecha_causacion = fecha_cierre

    # Fecha de vencimiento (configurable)
    meses_venc = (
        config.meses_vencimiento if config else MESES_VENCIMIENTO_DEFAULT
    )
    fecha_vencimiento = _sumar_meses(fecha_causacion, meses_venc)

    return {
        "anio": anio,
        "anios_antiguedad": anios,
        "dias_derecho": _r2(dias_derecho),
        "dias_bono_vacacional": _r2(dias_bono),
        "fecha_causacion": fecha_causacion,
        "fecha_vencimiento": fecha_vencimiento,
        "prorrateado": prorrateado,
        "meses_trabajados": meses_trabajados,
    }


def _sumar_meses(fecha, meses):
    """Suma meses a una fecha, ajustando el día si es necesario."""
    mes = fecha.month + meses
    anio = fecha.year + (mes - 1) // 12
    mes = ((mes - 1) % 12) + 1
    # Ajustar día si el mes destino tiene menos días
    import calendar
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    dia = min(fecha.day, ultimo_dia)
    return date(anio, mes, dia)


# ═══════════════════════════════════════════════════════════
#  VACACIONES FRACCIONADAS (al egreso)
# ═══════════════════════════════════════════════════════════

def calcular_vacaciones_fraccionadas(empleado, fecha_egreso, config=None):
    """
    Calcula las vacaciones fraccionadas al egreso.

    Fórmula:
        dias_fraccionados = (dias_vacaciones × meses_completos) / 12

    Se cuenta desde el último aniversario hasta la fecha de egreso.
    """
    from rrhh.models import ConfiguracionVacaciones

    if config is None:
        config = ConfiguracionVacaciones.objects.filter(
            empresa=empleado.empresa,
        ).first()

    fecha_ingreso = empleado.fecha_ingreso

    # Último aniversario antes del egreso
    anios = calcular_anios_antiguedad(fecha_ingreso, fecha_egreso)
    ultimo_aniversario = fecha_ingreso.replace(
        year=fecha_ingreso.year + anios
    )

    # Meses completos desde el último aniversario
    meses_fraccion = calcular_meses_fraccion(ultimo_aniversario, fecha_egreso)

    if meses_fraccion <= 0:
        return {
            "meses_fraccion": 0,
            "dias_vacaciones_fraccionadas": Decimal("0"),
            "dias_bono_fraccionados": Decimal("0"),
            "ultimo_aniversario": ultimo_aniversario,
        }

    # Días base según antigüedad actual
    dias_vac = Decimal(str(calcular_dias_vacaciones(anios, config)))
    dias_bono = Decimal(str(calcular_dias_bono_vacacional(anios, config)))

    # Fracción
    dias_vac_frac = _r2(dias_vac * meses_fraccion / 12)
    dias_bono_frac = _r2(dias_bono * meses_fraccion / 12)

    return {
        "meses_fraccion": meses_fraccion,
        "dias_vacaciones_fraccionadas": dias_vac_frac,
        "dias_bono_fraccionados": dias_bono_frac,
        "ultimo_aniversario": ultimo_aniversario,
    }


# ═══════════════════════════════════════════════════════════
#  VENCIMIENTO
# ═══════════════════════════════════════════════════════════

def calcular_vencimiento(saldo, config=None):
    """
    Calcula la fecha de vencimiento de un saldo.
    """
    from rrhh.models import ConfiguracionVacaciones

    if config is None:
        config = ConfiguracionVacaciones.objects.filter(
            empresa=saldo.empleado.empresa,
        ).first()

    meses = config.meses_vencimiento if config else MESES_VENCIMIENTO_DEFAULT
    fecha_causacion = date(saldo.anio, 12, 31)
    return _sumar_meses(fecha_causacion, meses)


def dias_por_vencer(saldo, dias_aviso=60):
    """
    Indica si un saldo está por vencer (dentro de los próximos `dias_aviso`).
    """
    if not saldo.fecha_limite_uso:
        return {
            "esta_por_vencer": False,
            "dias_restantes": None,
            "fecha_vencimiento": None,
        }

    hoy = date.today()
    dias = (saldo.fecha_limite_uso - hoy).days

    return {
        "esta_por_vencer": 0 <= dias <= dias_aviso,
        "dias_restantes": max(dias, 0),
        "fecha_vencimiento": saldo.fecha_limite_uso,
    }