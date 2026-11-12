"""
Cálculo de aportes al IVSS, Paro Forzoso (RPE) y BANAVIH.
"""
from decimal import Decimal, ROUND_HALF_UP


def r2(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ═══════════════════════════════════════════════════════════
#  IVSS (Seguro Social)
# ═══════════════════════════════════════════════════════════

def calcular_ivss(salario_mensual, salario_minimo, dias_periodo=30,
                  tasa_obrero=Decimal("0.04"), tasa_patronal=Decimal("0.09"),
                  tope_salarios=Decimal("5")):
    """
    Calcula el IVSS obrero y patronal.

    La base tiene un tope de N salarios mínimos.

    Args:
        salario_mensual: Decimal — salario del empleado
        salario_minimo: Decimal — salario mínimo vigente
        dias_periodo: días del periodo
        tasa_obrero: 4% por defecto
        tasa_patronal: 9% por defecto
        tope_salarios: 5 salarios mínimos por defecto

    Returns:
        dict con base, tope, ivss_obrero, ivss_patronal
    """
    salario = Decimal(str(salario_mensual))
    sm = Decimal(str(salario_minimo))

    # Tope: N × salario mínimo
    tope_mensual = sm * Decimal(str(tope_salarios))

    # Base de cálculo (min entre salario y tope)
    base_mensual = min(salario, tope_mensual)
    base_periodo = base_mensual * Decimal(str(dias_periodo)) / Decimal("30")

    ivss_obrero = base_periodo * Decimal(str(tasa_obrero))
    ivss_patronal = base_periodo * Decimal(str(tasa_patronal))

    return {
        "base_mensual": r2(base_mensual),
        "base_periodo": r2(base_periodo),
        "tope_mensual": r2(tope_mensual),
        "ivss_obrero": r2(ivss_obrero),
        "ivss_patronal": r2(ivss_patronal),
        "tasa_obrero": tasa_obrero,
        "tasa_patronal": tasa_patronal,
    }


# ═══════════════════════════════════════════════════════════
#  PARO FORZOSO (RPE)
# ═══════════════════════════════════════════════════════════

def calcular_rpe(salario_mensual, salario_minimo, dias_periodo=30,
                 tasa_obrero=Decimal("0.005"), tasa_patronal=Decimal("0.02"),
                 tope_salarios=Decimal("10")):
    """
    Calcula el Paro Forzoso (RPE).

    La base tiene un tope de 10 salarios mínimos.
    """
    salario = Decimal(str(salario_mensual))
    sm = Decimal(str(salario_minimo))

    tope_mensual = sm * Decimal(str(tope_salarios))
    base_mensual = min(salario, tope_mensual)
    base_periodo = base_mensual * Decimal(str(dias_periodo)) / Decimal("30")

    rpe_obrero = base_periodo * Decimal(str(tasa_obrero))
    rpe_patronal = base_periodo * Decimal(str(tasa_patronal))

    return {
        "base_mensual": r2(base_mensual),
        "base_periodo": r2(base_periodo),
        "tope_mensual": r2(tope_mensual),
        "rpe_obrero": r2(rpe_obrero),
        "rpe_patronal": r2(rpe_patronal),
    }


# ═══════════════════════════════════════════════════════════
#  BANAVIH (Vivienda)
# ═══════════════════════════════════════════════════════════

def calcular_banavih(salario_mensual, dias_periodo=30,
                     tasa_obrero=Decimal("0.01"), tasa_patronal=Decimal("0.02")):
    """
    Calcula el aporte al BANAVIH (sin tope).
    """
    salario = Decimal(str(salario_mensual))
    base_periodo = salario * Decimal(str(dias_periodo)) / Decimal("30")

    return {
        "base_periodo": r2(base_periodo),
        "banavih_obrero": r2(base_periodo * Decimal(str(tasa_obrero))),
        "banavih_patronal": r2(base_periodo * Decimal(str(tasa_patronal))),
    }


# ═══════════════════════════════════════════════════════════
#  INCES (solo patronal)
# ═══════════════════════════════════════════════════════════

def calcular_inces(salario_mensual, dias_periodo=30, tasa_patronal=Decimal("0.02")):
    """
    Calcula el aporte patronal al INCES.
    """
    salario = Decimal(str(salario_mensual))
    base_periodo = salario * Decimal(str(dias_periodo)) / Decimal("30")

    return {
        "base_periodo": r2(base_periodo),
        "inces_patronal": r2(base_periodo * Decimal(str(tasa_patronal))),
    }


# ═══════════════════════════════════════════════════════════
#  LOPCYMAT (solo patronal, según categoría de riesgo)
# ═══════════════════════════════════════════════════════════

def calcular_lopcymat(salario_mensual, categoria="I", dias_periodo=30):
    """
    Calcula el aporte patronal al LOPCYMAT según categoría de riesgo.
    """
    tasas = {
        "I": Decimal("0.0075"),
        "II": Decimal("0.015"),
        "III": Decimal("0.03"),
        "IV": Decimal("0.05"),
        "V": Decimal("0.10"),
    }
    tasa = tasas.get(categoria, Decimal("0.0075"))

    salario = Decimal(str(salario_mensual))
    base_periodo = salario * Decimal(str(dias_periodo)) / Decimal("30")

    return {
        "base_periodo": r2(base_periodo),
        "tasa": tasa,
        "categoria": categoria,
        "lopcymat_patronal": r2(base_periodo * tasa),
    }