# contabilidad/presupuesto_engine.py
from decimal import Decimal


def calcular_desviacion(monto_presupuesto, monto_real, tipo_cuenta):
    """
    Calcula la desviación entre el presupuesto y el real.
    
    Args:
        monto_presupuesto: Decimal con el monto presupuestado
        monto_real: Decimal con el monto real de la contabilidad
        tipo_cuenta: "INGRESO", "GASTO", "COSTO"
    
    Returns:
        dict con: presupuesto, real, diferencia, porcentaje, es_favorable, estado
    """
    presupuesto = Decimal(str(monto_presupuesto or 0))
    real = Decimal(str(monto_real or 0))
    
    diferencia = real - presupuesto
    porcentaje = (diferencia / presupuesto * 100) if presupuesto != 0 else Decimal("0")
    
    es_favorable = False
    
    # Lógica: 
    # - Para INGRESOS: si real > presupuesto → favorable
    # - Para GASTOS/COSTOS: si real < presupuesto → favorable (gastaste menos)
    if tipo_cuenta == "INGRESO":
        es_favorable = diferencia >= 0
    elif tipo_cuenta in ["GASTO", "COSTO"]:
        es_favorable = diferencia <= 0
    
    return {
        "presupuesto": presupuesto,
        "real": real,
        "diferencia": diferencia,
        "porcentaje": porcentaje,
        "es_favorable": es_favorable,
        "estado": "Favorable" if es_favorable else "Desfavorable",
    }


def obtener_meses():
    """Utilidad para iterar sobre los meses del presupuesto."""
    return [
        ("enero", "Enero"), ("febrero", "Febrero"), ("marzo", "Marzo"),
        ("abril", "Abril"), ("mayo", "Mayo"), ("junio", "Junio"),
        ("julio", "Julio"), ("agosto", "Agosto"), ("septiembre", "Septiembre"),
        ("octubre", "Octubre"), ("noviembre", "Noviembre"), ("diciembre", "Diciembre"),
    ]