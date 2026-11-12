"""
Cálculo de prestaciones sociales, utilidades, vacaciones y bono vacacional
según la LOTTT venezolana.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def r2(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ═══════════════════════════════════════════════════════════
#  SALARIO INTEGRAL
# ═══════════════════════════════════════════════════════════

def calcular_salario_integral(salario_normal_diario, dias_utilidades=30,
                              dias_bono_vacacional=15, factor_integracion=Decimal("1.0")):
    """
    Calcula el Salario Integral = Salario Normal + alícuotas.

    Alícuota Utilidades = (Salario Normal × Días Utilidades) / 360
    Alícuota Bono Vacacional = (Salario Normal × Días Bono Vac) / 360
    """
    snd = Decimal(str(salario_normal_diario))
    dias_util = Decimal(str(dias_utilidades))
    dias_bv = Decimal(str(dias_bono_vacacional))

    alicuota_utilidades = (snd * dias_util) / Decimal("360")
    alicuota_bono_vac = (snd * dias_bv) / Decimal("360")

    salario_integral = snd + alicuota_utilidades + alicuota_bono_vac

    return {
        "salario_normal_diario": r2(snd),
        "alicuota_utilidades": r2(alicuota_utilidades),
        "alicuota_bono_vacacional": r2(alicuota_bono_vac),
        "salario_integral_diario": r2(salario_integral),
        "salario_integral_mensual": r2(salario_integral * Decimal("30")),
    }


# ═══════════════════════════════════════════════════════════
#  PRESTACIONES SOCIALES
# ═══════════════════════════════════════════════════════════

def calcular_prestaciones_sociales(salario_integral_diario, fecha_ingreso, fecha_egreso,
                                    dias_trimestre=15, dias_anio=30, dias_adicionales=2):
    """
    Calcula las prestaciones sociales por los dos métodos (LOTTT Art. 142).

    Método A (Garantía): 15 días de salario integral por trimestre + 2 días por año
    Método B (Retroactivo): 30 días de salario integral por año de servicio
    Se paga el mayor.
    """
    sid = Decimal(str(salario_integral_diario))

    # Calcular antigüedad
    if isinstance(fecha_ingreso, str):
        fecha_ingreso = date.fromisoformat(fecha_ingreso)
    if isinstance(fecha_egreso, str):
        fecha_egreso = date.fromisoformat(fecha_egreso)

    dias_totales = (fecha_egreso - fecha_ingreso).days
    anios_servicio = dias_totales / 365.25

    # Método A: garantía trimestral
    trimestres = int(dias_totales / 91.25)  # 365/4
    dias_metodo_a = trimestres * dias_trimestre

    # Días adicionales por año (después del primer año)
    if anios_servicio > 1:
        anios_adicionales = int(anios_servicio) - 1
        dias_adicionales_total = 0
        for i in range(1, anios_adicionales + 1):
            dias_adicionales_total += i * dias_adicionales
        dias_metodo_a += dias_adicionales_total

    monto_metodo_a = sid * Decimal(str(dias_metodo_a))

    # Método B: retroactivo
    dias_metodo_b = Decimal(str(anios_servicio)) * Decimal(str(dias_anio))
    monto_metodo_b = sid * dias_metodo_b

    # Se paga el mayor
    if monto_metodo_a >= monto_metodo_b:
        metodo_aplicado = "A"
        monto_total = monto_metodo_a
    else:
        metodo_aplicado = "B"
        monto_total = monto_metodo_b

    return {
        "anios_servicio": round(anios_servicio, 2),
        "dias_totales": dias_totales,
        "trimestres": trimestres,
        "dias_metodo_a": dias_metodo_a,
        "monto_metodo_a": r2(monto_metodo_a),
        "dias_metodo_b": float(r2(dias_metodo_b)),
        "monto_metodo_b": r2(monto_metodo_b),
        "metodo_aplicado": metodo_aplicado,
        "monto_total": r2(monto_total),
    }


# ═══════════════════════════════════════════════════════════
#  UTILIDADES
# ═══════════════════════════════════════════════════════════

def calcular_utilidades(salario_normal_diario, meses_completos, dias_utilidades=30):
    """
    Calcula las utilidades (fraccionadas o completas).

    Utilidades = (Días utilidades / 12) × Meses completos × Salario diario
    """
    snd = Decimal(str(salario_normal_diario))
    meses = Decimal(str(meses_completos))
    dias = Decimal(str(dias_utilidades))

    dias_a_pagar = (dias / Decimal("12")) * meses
    monto = dias_a_pagar * snd

    return {
        "dias_utilidades_anio": dias_utilidades,
        "meses_completos": meses_completos,
        "dias_a_pagar": float(r2(dias_a_pagar)),
        "monto": r2(monto),
    }


# ═══════════════════════════════════════════════════════════
#  VACACIONES Y BONO VACACIONAL
# ═══════════════════════════════════════════════════════════

def calcular_dias_vacaciones(anios_antiguedad, dias_base=15, dias_max=30):
    """
    Días de vacaciones según antigüedad (LOTTT Art. 190).
    """
    if anios_antiguedad < 1:
        return dias_base
    return min(dias_base + (anios_antiguedad - 1), dias_max)


def calcular_dias_bono_vacacional(anios_antiguedad, dias_base=15, dias_max=30):
    """
    Días de bono vacacional según antigüedad (LOTTT Art. 192).
    """
    if anios_antiguedad < 1:
        return dias_base
    return min(dias_base + (anios_antiguedad - 1), dias_max)


def calcular_vacaciones_fraccionadas(salario_normal_diario, anios_antiguedad,
                                      meses_completos, dias_base=15, dias_max=30):
    """
    Calcula las vacaciones fraccionadas.
    """
    dias_anio = calcular_dias_vacaciones(anios_antiguedad, dias_base, dias_max)
    snd = Decimal(str(salario_normal_diario))
    meses = Decimal(str(meses_completos))

    dias_a_pagar = (Decimal(str(dias_anio)) / Decimal("12")) * meses
    monto = dias_a_pagar * snd

    return {
        "dias_vacaciones_anio": dias_anio,
        "meses_completos": meses_completos,
        "dias_a_pagar": float(r2(dias_a_pagar)),
        "monto": r2(monto),
    }


def calcular_bono_vacacional_fraccionado(salario_normal_diario, anios_antiguedad,
                                          meses_completos, dias_base=15, dias_max=30):
    """
    Calcula el bono vacacional fraccionado.
    """
    dias_anio = calcular_dias_bono_vacacional(anios_antiguedad, dias_base, dias_max)
    snd = Decimal(str(salario_normal_diario))
    meses = Decimal(str(meses_completos))

    dias_a_pagar = (Decimal(str(dias_anio)) / Decimal("12")) * meses
    monto = dias_a_pagar * snd

    return {
        "dias_bono_vacacional_anio": dias_anio,
        "meses_completos": meses_completos,
        "dias_a_pagar": float(r2(dias_a_pagar)),
        "monto": r2(monto),
    }