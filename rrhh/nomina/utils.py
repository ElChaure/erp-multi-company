"""
Utilidades para el motor de nómina.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def r2(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_meses_completos(fecha_inicio, fecha_fin):
    """
    Calcula los meses completos trabajados entre dos fechas.
    Se usa para utilidades y vacaciones fraccionadas.
    """
    if isinstance(fecha_inicio, str):
        fecha_inicio = date.fromisoformat(fecha_inicio)
    if isinstance(fecha_fin, str):
        fecha_fin = date.fromisoformat(fecha_fin)

    meses = (fecha_fin.year - fecha_inicio.year) * 12 + (fecha_fin.month - fecha_inicio.month)

    # Si el día del fin es menor al día de inicio, no se completó el mes
    if fecha_fin.day < fecha_inicio.day:
        meses -= 1

    return max(0, meses)


def calcular_anios_antiguedad(fecha_ingreso, fecha_referencia=None):
    """
    Calcula los años completos de antigüedad.
    """
    if fecha_referencia is None:
        fecha_referencia = date.today()

    if isinstance(fecha_ingreso, str):
        fecha_ingreso = date.fromisoformat(fecha_ingreso)

    anios = fecha_referencia.year - fecha_ingreso.year
    if (fecha_referencia.month, fecha_referencia.day) < (fecha_ingreso.month, fecha_ingreso.day):
        anios -= 1

    return max(0, anios)


def calcular_salario_diario(salario_mensual):
    """Convierte salario mensual a diario."""
    return r2(Decimal(str(salario_mensual)) / Decimal("30"))


def calcular_factor_integracion(dias_utilidades=30, dias_bono_vacacional=15,
                                 dias_aguinaldo=15):
    """
    Factor de integración salarial.

    Factor = 1 + (utilidades/360) + (bono_vac/360) + (aguinaldo/360)
    """
    util = Decimal(str(dias_utilidades)) / Decimal("360")
    bv = Decimal(str(dias_bono_vacacional)) / Decimal("360")
    agui = Decimal(str(dias_aguinaldo)) / Decimal("360")

    return Decimal("1") + util + bv + agui