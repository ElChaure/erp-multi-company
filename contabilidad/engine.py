# contabilidad/engine.py
from decimal import Decimal
from .constants import NATURALEZA_DEUDORA, NATURALEZA_ACREEDORA

def calcular_totales_lineas(lineas):
    """
    Recibe una lista de diccionarios con 'debito' y 'credito'.
    Retorna un diccionario con los totales y si cuadra.
    """
    total_debito = sum(Decimal(str(l.get("debito", 0))) for l in lineas)
    total_credito = sum(Decimal(str(l.get("credito", 0))) for l in lineas)
    diferencia = total_debito - total_credito
    
    return {
        "total_debito": total_debito,
        "total_credito": total_credito,
        "diferencia": diferencia,
        "cuadra": abs(diferencia) < Decimal("0.005"), # Tolerancia de redondeo
    }

def validar_asiento(lineas, periodo_abierto=True):
    """
    Valida que un asiento pueda ser contabilizado.
    Retorna una lista de errores (vacía si está OK).
    """
    errores = []
    
    # 1. Validar período
    if not periodo_abierto:
        errores.append("El período contable está cerrado.")
    
    # 2. Validar que tenga al menos 2 líneas
    if len(lineas) < 2:
        errores.append("Un asiento debe tener al menos 2 líneas.")
    
    # 3. Validar partida doble
    totales = calcular_totales_lineas(lineas)
    if not totales["cuadra"]:
        errores.append(f"El asiento no cuadra. Diferencia: {totales['diferencia']}")
    
    # 4. Validar que no haya líneas con débito y crédito a la vez (o ambas en cero)
    for l in lineas:
        debito = Decimal(str(l.get("debito", 0)))
        credito = Decimal(str(l.get("credito", 0)))
        if debito == 0 and credito == 0:
            errores.append("Hay una línea con débito y crédito en cero.")
        if debito > 0 and credito > 0:
            errores.append("Una línea no puede tener débito y crédito al mismo tiempo.")
            
    return errores

def calcular_saldo_final(saldo_inicial, debitos, creditos, naturaleza):
    """
    Calcula el saldo final de una cuenta según su naturaleza.
    - Si es Deudora: Saldo = Inicial + Débitos - Créditos
    - Si es Acreedora: Saldo = Inicial + Créditos - Débitos
    """
    saldo_inicial = Decimal(str(saldo_inicial))
    debitos = Decimal(str(debitos))
    creditos = Decimal(str(creditos))
    
    if naturaleza == NATURALEZA_DEUDORA:
        return saldo_inicial + debitos - creditos
    elif naturaleza == NATURALEZA_ACREEDORA:
        return saldo_inicial + creditos - debitos
    return Decimal("0")