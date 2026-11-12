from decimal import Decimal, ROUND_HALF_UP
from .constants import METODO_LINEA_RECTA, METODO_UNIDADES_PRODUCCION


def calcular_depreciacion_mensual(activo, unidades_producidas_mes=0):
    """
    Calcula el monto a depreciar en un mes según el método del activo.
    
    Args:
        activo: instancia de ActivoFijo.
        unidades_producidas_mes: solo para método de Unidades de Producción (Fase 4).
    
    Returns:
        Decimal con el monto a depreciar en el mes.
    """
    base = Decimal(str(activo.base_depreciable))

    if base <= 0:
        return Decimal("0.00")

    # 1. Línea Recta (por defecto y único funcional al 100% en esta fase)
    if activo.metodo_depreciacion == METODO_LINEA_RECTA:
        vida_meses = Decimal(str(activo.vida_util_anios)) * Decimal("12")
        if vida_meses == 0:
            return Decimal("0.00")
        monto = base / vida_meses
        return monto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 2. Unidades de Producción (Fase 4 — requiere módulo de producción)
    elif activo.metodo_depreciacion == METODO_UNIDADES_PRODUCCION:
        if not activo.total_unidades_estimadas or activo.total_unidades_estimadas == 0:
            return Decimal("0.00")
        tasa_unidad = base / Decimal(str(activo.total_unidades_estimadas))
        monto = tasa_unidad * Decimal(str(unidades_producidas_mes))
        return monto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 3. Métodos no implementados todavía: retornar 0 (evita errores silenciosos)
    return Decimal("0.00")