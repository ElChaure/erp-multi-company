"""
Cálculo del Impuesto Sobre la Renta (ISLR) - Venezuela.

Basado en el Art. 50 de la LISLR (tarifa progresiva).
"""
from decimal import Decimal, ROUND_HALF_UP


def r2(valor):
    """Redondea a 2 decimales."""
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ═══════════════════════════════════════════════════════════
#  TARIFA ISLR MENSUAL (referencia — se puede sobrescribir)
# ═══════════════════════════════════════════════════════════
# Formato: (limite_inferior, limite_superior, sustraendo, porcentaje)
TARIFA_ISLR_MENSUAL = [
    (Decimal("0.00"),      Decimal("1000.00"),   Decimal("0.00"),     Decimal("0.00")),
    (Decimal("1000.01"),   Decimal("1500.00"),   Decimal("0.00"),     Decimal("0.06")),
    (Decimal("1500.01"),   Decimal("2000.00"),   Decimal("30.00"),    Decimal("0.09")),
    (Decimal("2000.01"),   Decimal("2500.00"),   Decimal("75.00"),    Decimal("0.12")),
    (Decimal("2500.01"),   Decimal("3000.00"),   Decimal("135.00"),   Decimal("0.16")),
    (Decimal("3000.01"),   Decimal("4000.00"),   Decimal("175.00"),   Decimal("0.20")),
    (Decimal("4000.01"),   Decimal("6000.00"),   Decimal("335.00"),   Decimal("0.24")),
    (Decimal("6000.01"),   Decimal("8000.00"),   Decimal("815.00"),   Decimal("0.28")),
    (Decimal("8000.01"),   Decimal("10000.00"),  Decimal("1375.00"),  Decimal("0.32")),
    (Decimal("10000.01"),  Decimal("9999999"),   Decimal("2015.00"),  Decimal("0.34")),
]


def calcular_islr_mensual(base_gravable):
    """
    Calcula el ISLR mensual aplicando la tarifa progresiva.

    Args:
        base_gravable: Decimal — enriquecimiento neto mensual

    Returns:
        dict con:
            - base: la base usada
            - tarifa: el rango aplicado
            - sustraendo: el sustraendo del rango
            - porcentaje: la tasa aplicada
            - islr: el impuesto calculado
    """
    base = Decimal(str(base_gravable))

    if base <= 0:
        return {
            "base": Decimal("0.00"),
            "tarifa": TARIFA_ISLR_MENSUAL[0],
            "sustraendo": Decimal("0.00"),
            "porcentaje": Decimal("0.00"),
            "islr": Decimal("0.00"),
        }

    # Buscar el rango
    rango = None
    for r in TARIFA_ISLR_MENSUAL:
        lim_inf, lim_sup, sustraendo, porcentaje = r
        if base >= lim_inf and base <= lim_sup:
            rango = r
            break

    if rango is None:
        # Si excede el máximo, usar el último rango
        rango = TARIFA_ISLR_MENSUAL[-1]

    _, _, sustraendo, porcentaje = rango

    # ISLR = (base × porcentaje) − sustraendo
    islr = (base * porcentaje) - sustraendo

    if islr < 0:
        islr = Decimal("0.00")

    return {
        "base": r2(base),
        "tarifa": rango,
        "sustraendo": sustraendo,
        "porcentaje": porcentaje,
        "islr": r2(islr),
    }


def calcular_islr_periodo(base_gravable_periodo, tipo_periodo="mensual", dias_periodo=30):
    """
    Calcula el ISLR correspondiente a un periodo (no mensual).

    Estrategia:
      1. Se mensualiza la base (base_periodo × 30 / dias_periodo)
      2. Se calcula el ISLR mensual
      3. Se proporcionaliza el ISLR al periodo (islr_mensual × dias_periodo / 30)

    Args:
        base_gravable_periodo: Decimal — base gravable del periodo
        tipo_periodo: 'semanal' | 'catorcenal' | 'quincenal' | 'mensual'
        dias_periodo: días del periodo

    Returns:
        dict con desglose
    """
    base = Decimal(str(base_gravable_periodo))

    if base <= 0:
        return {
            "base_periodo": Decimal("0.00"),
            "base_mensual": Decimal("0.00"),
            "islr_mensual": Decimal("0.00"),
            "islr_periodo": Decimal("0.00"),
            "tarifa": TARIFA_ISLR_MENSUAL[0],
        }

    # Mensualizar
    factor = Decimal("30") / Decimal(str(dias_periodo))
    base_mensual = base * factor

    # Calcular ISLR mensual
    resultado = calcular_islr_mensual(base_mensual)

    # Proporcionalizar al periodo
    islr_periodo = resultado["islr"] * Decimal(str(dias_periodo)) / Decimal("30")

    return {
        "base_periodo": r2(base),
        "base_mensual": r2(base_mensual),
        "islr_mensual": resultado["islr"],
        "islr_periodo": r2(islr_periodo),
        "tarifa": resultado["tarifa"],
        "sustraendo": resultado["sustraendo"],
        "porcentaje": resultado["porcentaje"],
    }